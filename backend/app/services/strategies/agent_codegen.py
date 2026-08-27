from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import shutil
import tempfile
import uuid
from decimal import Decimal
from typing import Any

from app.config import settings
from app.db import get_sync_session
from app.engines.ai.base import normalize_usage
from app.models.worker_task import WorkerTask
from app.services.strategies.agent_runtime import (
    AgentCancelledError,
    AgentRunResult,
    build_agent_runtime,
)
from app.services.strategies.agent_sandbox import (
    read_scene_codes,
    validate_workdir,
    write_sandbox,
)
from app.services.strategies.base import CodegenOutcome

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是渲染代码工程师。工作目录里有：

- `input.json`：待实现的镜头叙事，每个镜头有 scene_index / narration / description / beats。
- `STYLE.md`：必须遵守的风格与画幅约束。
- `scenes/`：你的产出目录。

任务：为 input.json 里的**每一个**镜头写一个文件 `scenes/scene_NN.py`（NN 为两位数的 scene_index，从 00 开始），一个镜头一个文件，不得合并或省略。

**文件内容契约（写错会渲染出黑屏，而校验仍会通过——务必遵守）**：
每个文件只写该镜头 `construct()` 方法体内的语句，顶格书写，渲染引擎会把整个文件缩进后塞进
`class MainScene(Scene)` 的 `def _scene_NN(self):` 里。因此：

- 直接写 `self.play(...)` / `self.wait(...)` 这类语句，文件第一行就是第一条语句。
- **禁止**写 `class XxxScene(Scene)`、`def construct(self)` 或任何其它类/函数结构定义——
  写了只会定义一个从不被执行的类，画面全黑。
- **禁止** `from manim import *` 或 `import manim`，环境已注入，`np` 可直接使用；
  确需 math / random / itertools 等标准库时可直接写 import，系统会自动提升到模块级。
- 镜头之间不得靠裸变量互相引用，跨镜头共享一律走 `self.xxx` 属性。

`STYLE.md` 的「引擎约束」一节是硬性规范（API 版本、高频崩溃点、时长匹配、退场纪律等），
逐条遵守，不要凭直觉命名类或参数。

工作方式：先读取 input.json 和 STYLE.md，再逐镜头写入代码。写完后调用 validate 工具校验。
校验报错会指出出问题的镜头编号，你据此只修改对应文件，然后重新校验。**必须**反复迭代直到
validate 返回通过为止，通过之后才能结束。不要在校验尚未通过时就宣称完成。"""


def is_task_cancelled(task_id: Any) -> bool:
    if task_id is None:
        return False
    db = get_sync_session()
    try:
        task = db.get(WorkerTask, task_id)
        return task is not None and task.status == "cancelled"
    except Exception:
        logger.exception("[AgentCodegen] 取消状态查询失败，按未取消处理")
        return False
    finally:
        db.close()


async def record_agent_call(
    *,
    provider: str,
    model: str,
    business: str,
    input_summary: dict,
    output: str,
    usage: dict[str, Any] | None,
    total_cost_usd: float | None,
    status: str,
    error_message: str | None = None,
) -> None:
    """一次 Agent 执行记一条 ai_call_records（best-effort，失败不影响主流程）。"""
    from app.db import AsyncSessionLocal
    from app.models.ai_call_record import AICallRecord

    normalized = normalize_usage(usage)
    if total_cost_usd is not None:
        normalized["total_cost"] = Decimal(str(total_cost_usd))
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                AICallRecord(
                    id=uuid.uuid4(),
                    provider=provider,
                    model=model,
                    business=business,
                    request_type="agent",
                    status=status,
                    input=input_summary,
                    output=output,
                    usage=normalized["usage"],
                    prompt_tokens=normalized["prompt_tokens"],
                    completion_tokens=normalized["completion_tokens"],
                    total_tokens=normalized["total_tokens"],
                    cached_tokens=normalized["cached_tokens"],
                    reasoning_tokens=normalized["reasoning_tokens"],
                    input_cost=normalized["input_cost"],
                    output_cost=normalized["output_cost"],
                    total_cost=normalized["total_cost"],
                    error_message=error_message,
                )
            )
            await db.commit()
    except Exception:
        logger.exception("[AgentCodegen] ai_call_records 写入失败，忽略")


def _agent_provider_config():
    from app.engines.ai.factory import _provider_settings_from_db

    config = _provider_settings_from_db("code_generation")
    if config is None:
        raise ValueError(
            "Agent 模式需要为 code_generation 配置 anthropic 或 openai provider"
        )
    if config.provider_type.lower() not in {"anthropic", "openai"}:
        raise ValueError(
            "Agent 模式仅支持 anthropic 或 openai provider，"
            f"当前为 {config.provider_type}"
        )
    return config


class AgentCodegenStrategy:
    def __init__(self, agent_query=None, *, runtime_factory=None, openai_runner=None):
        self._agent_query = agent_query
        self._runtime_factory = runtime_factory
        self._openai_runner = openai_runner

    async def run(
        self,
        *,
        scenes,
        render_engine,
        style_components,
        aspect_ratio,
        rejection_context,
        previous_code_scenes,
        task_id,
    ) -> CodegenOutcome:
        if render_engine != "manim":
            raise ValueError(
                f"Agent 模式目前只支持 manim 渲染引擎，当前为 {render_engine}"
            )
        if previous_code_scenes:
            logger.warning(
                "[AgentCodegen] previous_code_scenes 暂未被 Agent 模式使用，已忽略"
            )

        config = _agent_provider_config()
        if self._runtime_factory is not None:
            runtime = self._runtime_factory(config)
        else:
            runtime = build_agent_runtime(
                config,
                claude_query=self._agent_query,
                openai_runner=self._openai_runner,
            )

        workdir = tempfile.mkdtemp(prefix="agent-codegen-")
        trace: dict[str, Any] = {
            "execution_mode": "agent",
            "provider": runtime.provider,
            "sdk_name": runtime.sdk_name,
            "sdk_version": runtime.sdk_version,
            "model": runtime.model,
            "tool_calls": [],
            "usage": {},
            "resumed": False,
            "total_cost_usd": 0.0,
            "num_turns": 0,
            "max_turns": settings.AGENT_MAX_TURNS,
        }
        recorded = False
        try:
            write_sandbox(
                workdir,
                scenes=scenes,
                style_components=style_components,
                aspect_ratio=aspect_ratio,
                render_engine=render_engine,
            )
            first_input = "请开始执行代码生成任务。"
            if rejection_context:
                first_input += (
                    "\n\n这是一次重新生成，上一版被驳回。驳回意见：\n"
                    + json.dumps(rejection_context, ensure_ascii=False)
                )

            first_result = await self._run_once(
                runtime=runtime,
                instructions=_SYSTEM_PROMPT,
                input_text=first_input,
                workdir=workdir,
                scenes=scenes,
                render_engine=render_engine,
                continuation=None,
                task_id=task_id,
            )
            _accumulate_trace(trace, first_result)

            is_valid, errors = await validate_workdir(workdir, scenes, render_engine)
            if first_result.status != "success":
                is_valid = False
                errors = f"Agent 未正常结束，status = {first_result.status}"

            if not is_valid:
                logger.info("[AgentCodegen] 平台回读校验未过，续跑一次")
                trace["resumed"] = True
                second_result = await self._run_once(
                    runtime=runtime,
                    instructions=_SYSTEM_PROMPT,
                    input_text=(
                        "平台侧校验仍未通过，报错如下，请继续修改 scenes/ 下的文件"
                        f"直到 validate 通过：\n{errors}"
                    ),
                    workdir=workdir,
                    scenes=scenes,
                    render_engine=render_engine,
                    continuation=first_result.continuation,
                    task_id=task_id,
                )
                _accumulate_trace(trace, second_result)
                is_valid, errors = await validate_workdir(
                    workdir, scenes, render_engine
                )
                if second_result.status != "success":
                    is_valid = False
                    errors = f"Agent 未正常结束，status = {second_result.status}"

            if not is_valid:
                await record_agent_call(
                    provider=runtime.provider,
                    model=runtime.model,
                    business="code_generation",
                    input_summary=_input_summary(
                        scenes, style_components, runtime.provider, runtime.model
                    ),
                    output=trace.get("result_text", ""),
                    usage=trace.get("usage"),
                    total_cost_usd=trace["total_cost_usd"],
                    status="failed",
                    error_message=errors[:2000],
                )
                recorded = True
                raise ValueError(f"Agent 模式代码校验未通过：\n{errors[:2000]}")

            codes = read_scene_codes(workdir, len(scenes))
            merged_scenes = [
                {**scene, "code": codes[i]} for i, scene in enumerate(scenes)
            ]
            await record_agent_call(
                provider=runtime.provider,
                model=runtime.model,
                business="code_generation",
                input_summary=_input_summary(
                    scenes, style_components, runtime.provider, runtime.model
                ),
                output=trace.get("result_text", ""),
                usage=trace.get("usage"),
                total_cost_usd=trace["total_cost_usd"],
                status="success",
            )
            recorded = True
            trace["validated_first_pass"] = not trace["resumed"]
            return CodegenOutcome(
                scenes=merged_scenes,
                ai_model=runtime.model,
                trace=trace,
            )
        except AgentCancelledError as exc:
            if not recorded:
                await self._record_failure(
                    runtime, scenes, style_components, trace, "cancelled", exc
                )
            raise
        except Exception as exc:
            if not recorded:
                await self._record_failure(
                    runtime, scenes, style_components, trace, "failed", exc
                )
            raise
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    async def _record_failure(
        self, runtime, scenes, style_components, trace, status, exc
    ) -> None:
        await record_agent_call(
            provider=runtime.provider,
            model=runtime.model,
            business="code_generation",
            input_summary=_input_summary(
                scenes, style_components, runtime.provider, runtime.model
            ),
            output=trace.get("result_text", ""),
            usage=trace.get("usage"),
            total_cost_usd=trace.get("total_cost_usd"),
            status=status,
            error_message=str(exc)[:2000],
        )

    async def _run_once(
        self,
        *,
        runtime,
        instructions,
        input_text,
        workdir,
        scenes,
        render_engine,
        continuation,
        task_id,
    ) -> AgentRunResult:
        run_task = asyncio.create_task(
            runtime.run(
                instructions=instructions,
                input_text=input_text,
                workdir=workdir,
                scenes=scenes,
                render_engine=render_engine,
                continuation=continuation,
                is_cancelled=lambda: is_task_cancelled(task_id),
            )
        )
        cancel_task = asyncio.create_task(_wait_until_cancelled(task_id))
        try:
            done, _ = await asyncio.wait(
                {run_task, cancel_task},
                timeout=settings.AGENT_TIMEOUT_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                run_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await run_task
                raise ValueError(
                    f"Agent 执行超时（>{settings.AGENT_TIMEOUT_SECONDS}s）"
                )
            if cancel_task in done and cancel_task.result():
                run_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await run_task
                raise AgentCancelledError("task cancelled during agent execution")
            return await run_task
        finally:
            cancel_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cancel_task


async def _wait_until_cancelled(task_id: Any) -> bool:
    if task_id is None:
        await asyncio.Future()
    while True:
        if is_task_cancelled(task_id):
            return True
        await asyncio.sleep(1)


def _accumulate_trace(trace: dict[str, Any], result: AgentRunResult) -> None:
    trace["result_status"] = result.status
    trace["result_text"] = result.final_output
    trace["tool_calls"].extend(result.tool_calls)
    trace["num_turns"] += result.num_turns
    if result.total_cost_usd is not None:
        trace["total_cost_usd"] += result.total_cost_usd
    trace["usage"] = _merge_usage(trace.get("usage") or {}, result.usage)


def _merge_usage(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    if not right:
        return dict(left)
    merged = dict(left)
    for key in ("requests", "input_tokens", "output_tokens", "total_tokens"):
        merged[key] = int(left.get(key, 0) or 0) + int(right.get(key, 0) or 0)
    for details_key, value_keys in (
        ("input_tokens_details", ("cached_tokens", "cache_write_tokens")),
        ("output_tokens_details", ("reasoning_tokens",)),
    ):
        old_details = left.get(details_key) or {}
        new_details = right.get(details_key) or {}
        merged[details_key] = {
            key: int(old_details.get(key, 0) or 0)
            + int(new_details.get(key, 0) or 0)
            for key in value_keys
        }
    return merged


def _input_summary(
    scenes, style_components, provider: str, model: str
) -> dict[str, Any]:
    return {
        "scene_count": len(scenes),
        "style_categories": sorted(style_components.keys()),
        "provider": provider,
        "model": model,
        "max_turns": settings.AGENT_MAX_TURNS,
    }
