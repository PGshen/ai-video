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
from app.models.worker_task import WorkerTask
from app.services.strategies.agent_sandbox import (
    build_validate_server,
    read_scene_codes,
    validate_workdir,
    write_sandbox,
)
from app.services.strategies.base import CodegenOutcome

logger = logging.getLogger(__name__)


def _tool_target(block) -> str:
    """从工具调用块里摘出最能说明「在动哪个文件」的一小段，供日志使用。"""
    payload = getattr(block, "input", None)
    if not isinstance(payload, dict):
        return ""
    for key in ("file_path", "path", "pattern", "command"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""

AGENT_TOOL_WHITELIST = ["Read", "Write", "Edit", "Glob"]

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

工作方式：写完后调用 `validate` 工具校验。校验报错会指出出问题的镜头编号，你据此只修改对应文件，然后重新校验。**必须**反复迭代直到 validate 返回通过为止，通过之后才能结束。不要在校验尚未通过时就宣称完成。"""


class AgentCancelledError(Exception):
    """任务在 Agent 执行途中被取消。"""


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
    model: str,
    business: str,
    input_summary: dict,
    output: str,
    total_cost_usd: float | None,
    status: str,
    error_message: str | None = None,
) -> None:
    """一次 Agent 执行记一条 ai_call_records（best-effort，失败不影响主流程）。"""
    from app.db import AsyncSessionLocal
    from app.models.ai_call_record import AICallRecord

    try:
        async with AsyncSessionLocal() as db:
            db.add(
                AICallRecord(
                    id=uuid.uuid4(),
                    provider="anthropic",
                    model=model,
                    business=business,
                    request_type="agent",
                    status=status,
                    input=input_summary,
                    output=output,
                    total_cost=(
                        Decimal(str(total_cost_usd))
                        if total_cost_usd is not None
                        else None
                    ),
                    error_message=error_message,
                )
            )
            await db.commit()
    except Exception:
        logger.exception("[AgentCodegen] ai_call_records 写入失败，忽略")


class AgentCodegenStrategy:
    def __init__(self, agent_query=None):
        self._agent_query = agent_query

    def _query(self):
        if self._agent_query is not None:
            return self._agent_query
        from claude_agent_sdk import query

        return query

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
        agent_env, model = _agent_env_and_model()
        workdir = tempfile.mkdtemp(prefix="agent-codegen-")
        trace: dict[str, Any] = {
            "execution_mode": "agent",
            "tool_calls": [],
            "resumed": False,
            "total_cost_usd": 0.0,
            "num_turns": 0,
            "max_turns": settings.AGENT_MAX_TURNS,
            "sdk_version": _sdk_version(),
            "model": model,
        }
        try:
            write_sandbox(
                workdir,
                scenes=scenes,
                style_components=style_components,
                aspect_ratio=aspect_ratio,
                render_engine=render_engine,
            )
            server, tool_name = build_validate_server(workdir, scenes, render_engine)

            prompt = _SYSTEM_PROMPT
            if rejection_context:
                prompt += (
                    "\n\n这是一次重新生成，上一版被驳回。驳回意见：\n"
                    + json.dumps(rejection_context, ensure_ascii=False)
                )

            session_id = await self._run_once(
                prompt=prompt,
                server=server,
                tool_name=tool_name,
                workdir=workdir,
                trace=trace,
                task_id=task_id,
                resume=None,
                agent_env=agent_env,
                model=model,
            )

            is_valid, errors = await validate_workdir(workdir, scenes, render_engine)
            subtype_error = _subtype_error(trace)
            if subtype_error:
                is_valid, errors = False, subtype_error
            if not is_valid:
                # Agent 认为完成了，平台判定未过 —— 只给一次续跑机会
                logger.info("[AgentCodegen] 平台回读校验未过，resume 续跑一次")
                trace["resumed"] = True
                await self._run_once(
                    prompt=(
                        "平台侧校验仍未通过，报错如下，请继续修改 scenes/ 下的文件"
                        f"直到 validate 通过：\n{errors}"
                    ),
                    server=server,
                    tool_name=tool_name,
                    workdir=workdir,
                    trace=trace,
                    task_id=task_id,
                    resume=session_id,
                    agent_env=agent_env,
                    model=model,
                )
                is_valid, errors = await validate_workdir(
                    workdir, scenes, render_engine
                )
                subtype_error = _subtype_error(trace)
                if subtype_error:
                    is_valid, errors = False, subtype_error

            if not is_valid:
                await record_agent_call(
                    model=model,
                    business="code_generation",
                    input_summary=_input_summary(scenes, style_components, model),
                    output="",
                    total_cost_usd=trace["total_cost_usd"],
                    status="failed",
                    error_message=errors[:2000],
                )
                raise ValueError(f"Agent 模式代码校验未通过：\n{errors[:2000]}")

            codes = read_scene_codes(workdir, len(scenes))
            merged_scenes = [
                {**scene, "code": codes[i]} for i, scene in enumerate(scenes)
            ]

            await record_agent_call(
                model=model,
                business="code_generation",
                input_summary=_input_summary(scenes, style_components, model),
                output=trace.get("result_text", ""),
                total_cost_usd=trace["total_cost_usd"],
                status="success",
            )
            trace["validated_first_pass"] = not trace["resumed"]
            return CodegenOutcome(
                scenes=merged_scenes,
                ai_model=model,
                trace=trace,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    async def _run_once(
        self, *, prompt, server, tool_name, workdir, trace, task_id, resume,
        agent_env, model,
    ) -> str | None:
        try:
            return await asyncio.wait_for(
                self._stream(
                    prompt=prompt,
                    server=server,
                    tool_name=tool_name,
                    workdir=workdir,
                    trace=trace,
                    task_id=task_id,
                    resume=resume,
                    agent_env=agent_env,
                    model=model,
                ),
                timeout=settings.AGENT_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            raise ValueError(
                f"Agent 执行超时（>{settings.AGENT_TIMEOUT_SECONDS}s）"
            ) from exc

    async def _stream(
        self, *, prompt, server, tool_name, workdir, trace, task_id, resume,
        agent_env, model,
    ) -> str | None:
        options = _build_options(
            server, tool_name, workdir, resume, agent_env=agent_env, model=model
        )
        session_id = None
        # M-3：每轮重新判定，不沿用上一轮的 subtype
        trace["result_subtype"] = None
        stream = self._query()(prompt=prompt, options=options)
        async with contextlib.aclosing(stream) as messages:
            async for message in messages:
                if is_task_cancelled(task_id):
                    logger.info("[AgentCodegen] 任务已取消，中断 Agent 循环")
                    await record_agent_call(
                        model=model,
                        business="code_generation",
                        input_summary={"model": model},
                        output="",
                        total_cost_usd=trace.get("total_cost_usd"),
                        status="cancelled",
                        error_message="task cancelled during agent execution",
                    )
                    raise AgentCancelledError("task cancelled during agent execution")

                for block in getattr(message, "content", []) or []:
                    name = getattr(block, "name", None)
                    if name:
                        trace["tool_calls"].append(name)
                        logger.info(
                            "[AgentCodegen] 第 %d 次工具调用：%s %s",
                            len(trace["tool_calls"]),
                            name,
                            _tool_target(block),
                        )
                    else:
                        text = (getattr(block, "text", "") or "").strip()
                        if text:
                            logger.info(
                                "[AgentCodegen] %s",
                                text if len(text) <= 500 else text[:500] + "…",
                            )

                if getattr(message, "session_id", None):
                    session_id = message.session_id

                if _is_result_message(message):
                    trace["result_subtype"] = message.subtype
                    trace["result_text"] = getattr(message, "result", "") or ""
                    cost = getattr(message, "total_cost_usd", None)
                    if cost is not None:
                        # SDK 的 total_cost_usd 是「会话累计值」而非本轮增量
                        # （见 types.py ConversationResetMessage 文档串：running
                        # totals reported on subsequent ResultMessage objects），
                        # resume 续跑仍是同一 session，因此取最新值而不是累加。
                        trace["total_cost_usd"] = float(cost)
                    turns = getattr(message, "num_turns", None)
                    if turns:
                        # 与 total_cost_usd 同为会话累计值，取最新上报值。
                        trace["num_turns"] = int(turns)
                    logger.info(
                        "[AgentCodegen] Agent 回合结束：subtype=%s 累计 %s 轮 / $%s / %d 次工具调用",
                        trace["result_subtype"],
                        trace.get("num_turns"),
                        trace.get("total_cost_usd"),
                        len(trace["tool_calls"]),
                    )
        return session_id


def _sdk_version() -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("claude-agent-sdk")
    except PackageNotFoundError:  # pragma: no cover - 仅在未安装 SDK 时
        return None


def _subtype_error(trace: dict[str, Any]) -> str | None:
    """Agent 未以 success 收尾时，无论沙箱里残留什么代码都判失败。"""
    subtype = trace.get("result_subtype")
    if subtype is None:
        return "Agent 未返回结果消息（result subtype 缺失）"
    if subtype != "success":
        return f"Agent 未正常结束，result subtype = {subtype}"
    return None


def _is_result_message(message: Any) -> bool:
    """区分 ResultMessage 与同样带 subtype 的 SystemMessage。"""
    return hasattr(message, "subtype") and hasattr(message, "total_cost_usd")


def _build_options(server, tool_name, workdir, resume, *, agent_env, model):
    from claude_agent_sdk import ClaudeAgentOptions

    kwargs = dict(
        model=model,
        cwd=workdir,
        setting_sources=[],
        permission_mode="acceptEdits",
        max_turns=settings.AGENT_MAX_TURNS,
        max_budget_usd=settings.AGENT_MAX_BUDGET_USD,
        mcp_servers={"codegen": server},
        allowed_tools=[*AGENT_TOOL_WHITELIST, tool_name],
        tools=list(AGENT_TOOL_WHITELIST),
        env=agent_env,
    )
    if resume:
        kwargs["resume"] = resume
    return ClaudeAgentOptions(**kwargs)


# 会改变请求路由或鉴权来源的变量：一律显式置空，不让宿主机环境渗进 Agent 会话
_ROUTING_OVERRIDES = (
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BEDROCK_BASE_URL",
    "ANTHROPIC_VERTEX_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "AWS_BEARER_TOKEN_BEDROCK",
)


def _agent_env_and_model() -> tuple[dict[str, str], str]:
    """从 provider 配置取 Anthropic 凭证与模型。

    没有可用的 anthropic provider 时直接失败——SDK 会把 worker 容器的整个
    os.environ 透给 CLI，静默跑起来会用到宿主残留的 key，或耗满预算后
    才以含糊的鉴权错误结束。
    """
    from app.engines.ai.factory import _provider_settings_from_db

    config = _provider_settings_from_db("code_generation")
    if config is None or config.provider_type != "anthropic":
        raise ValueError("Agent 模式需要为 code_generation 配置 anthropic provider")

    # SDK 是 {**os.environ, **options.env} 合并，宿主机上任何供应商路由变量都会
    # 被继承进来，且 CLAUDE_CODE_USE_BEDROCK / _VERTEX 的优先级压过
    # ANTHROPIC_BASE_URL——平台里配的网关会被静默忽略、请求打到别处去。
    # 显式置空来中和它们，让路由只由这里的配置决定。
    env = {name: "" for name in _ROUTING_OVERRIDES}
    env["ANTHROPIC_API_KEY"] = config.api_key
    # base_url 为空表示走官方端点：仍要显式置空，否则宿主机的
    # ANTHROPIC_BASE_URL 会漏进来
    env["ANTHROPIC_BASE_URL"] = config.base_url or ""
    # spec：默认模型 settings.AGENT_MODEL，可被 provider 配置里的模型行覆盖
    return env, config.model or settings.AGENT_MODEL


def _input_summary(scenes, style_components, model: str) -> dict:
    return {
        "scene_count": len(scenes),
        "style_categories": sorted(style_components.keys()),
        "model": model,
        "max_turns": settings.AGENT_MAX_TURNS,
    }
