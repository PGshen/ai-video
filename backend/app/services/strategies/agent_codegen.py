from __future__ import annotations

import asyncio
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

AGENT_TOOL_WHITELIST = ["Read", "Write", "Edit", "Glob"]

_SYSTEM_PROMPT = """你是渲染代码工程师。工作目录里有：

- `input.json`：待实现的镜头叙事，每个镜头有 scene_index / narration / description / beats。
- `STYLE.md`：必须遵守的风格与画幅约束。
- `scenes/`：你的产出目录。

任务：为 input.json 里的**每一个**镜头写一个文件 `scenes/scene_NN.py`（NN 为两位数的 scene_index，从 00 开始），一个镜头一个文件，不得合并或省略。

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
        workdir = tempfile.mkdtemp(prefix="agent-codegen-")
        trace: dict[str, Any] = {
            "execution_mode": "agent",
            "tool_calls": [],
            "resumed": False,
            "total_cost_usd": 0.0,
            "num_turns": 0,
            "max_turns": settings.AGENT_MAX_TURNS,
            "sdk_version": _sdk_version(),
            "model": settings.AGENT_MODEL,
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
                )
                is_valid, errors = await validate_workdir(
                    workdir, scenes, render_engine
                )
                subtype_error = _subtype_error(trace)
                if subtype_error:
                    is_valid, errors = False, subtype_error

            if not is_valid:
                await record_agent_call(
                    model=settings.AGENT_MODEL,
                    business="code_generation",
                    input_summary=_input_summary(scenes, style_components),
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
                model=settings.AGENT_MODEL,
                business="code_generation",
                input_summary=_input_summary(scenes, style_components),
                output=trace.get("result_text", ""),
                total_cost_usd=trace["total_cost_usd"],
                status="success",
            )
            trace["validated_first_pass"] = not trace["resumed"]
            return CodegenOutcome(
                scenes=merged_scenes,
                ai_model=settings.AGENT_MODEL,
                trace=trace,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    async def _run_once(
        self, *, prompt, server, tool_name, workdir, trace, task_id, resume
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
                ),
                timeout=settings.AGENT_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            raise ValueError(
                f"Agent 执行超时（>{settings.AGENT_TIMEOUT_SECONDS}s）"
            ) from exc

    async def _stream(
        self, *, prompt, server, tool_name, workdir, trace, task_id, resume
    ) -> str | None:
        options = _build_options(server, tool_name, workdir, resume)
        session_id = None
        async for message in self._query()(prompt=prompt, options=options):
            if is_task_cancelled(task_id):
                logger.info("[AgentCodegen] 任务已取消，中断 Agent 循环")
                await record_agent_call(
                    model=settings.AGENT_MODEL,
                    business="code_generation",
                    input_summary={"model": settings.AGENT_MODEL},
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


def _build_options(server, tool_name, workdir, resume):
    from claude_agent_sdk import ClaudeAgentOptions

    kwargs = dict(
        model=settings.AGENT_MODEL,
        cwd=workdir,
        setting_sources=[],
        permission_mode="acceptEdits",
        max_turns=settings.AGENT_MAX_TURNS,
        max_budget_usd=settings.AGENT_MAX_BUDGET_USD,
        mcp_servers={"codegen": server},
        allowed_tools=[*AGENT_TOOL_WHITELIST, tool_name],
        tools=list(AGENT_TOOL_WHITELIST),
        env=_agent_env(),
    )
    if resume:
        kwargs["resume"] = resume
    return ClaudeAgentOptions(**kwargs)


def _agent_env() -> dict[str, str]:
    """从 provider 配置取 Anthropic 凭证。base_url 为空则走官方端点。"""
    from app.engines.ai.factory import _provider_settings_from_db

    config = _provider_settings_from_db("code_generation")
    env: dict[str, str] = {}
    if config is not None and config.provider_type == "anthropic":
        env["ANTHROPIC_API_KEY"] = config.api_key
        if config.base_url:
            env["ANTHROPIC_BASE_URL"] = config.base_url
    return env


def _input_summary(scenes, style_components) -> dict:
    return {
        "scene_count": len(scenes),
        "style_categories": sorted(style_components.keys()),
        "model": settings.AGENT_MODEL,
        "max_turns": settings.AGENT_MAX_TURNS,
    }
