from __future__ import annotations

import contextlib
import logging
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Callable

from app.config import settings
from app.engines.ai.live_preview import LiveLLMPreview
from app.engines.ai.factory import ProviderSettings
from app.services.strategies.agent_runtime import AgentCancelledError, AgentRunResult
from app.services.strategies.agent_sandbox import build_validate_server

logger = logging.getLogger(__name__)

CLAUDE_TOOL_WHITELIST = ["Read", "Write", "Edit", "Glob"]


def _tool_target(block: Any) -> str:
    payload = getattr(block, "input", None)
    if not isinstance(payload, dict):
        return ""
    for key in ("file_path", "path", "pattern", "command"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _sdk_version() -> str | None:
    try:
        return version("claude-agent-sdk")
    except PackageNotFoundError:  # pragma: no cover - 仅在未安装 SDK 时
        return None


def _is_result_message(message: Any) -> bool:
    return hasattr(message, "subtype") and hasattr(message, "total_cost_usd")


class ClaudeAgentRuntime:
    provider = "anthropic"
    sdk_name = "claude-agent-sdk"

    def __init__(self, config: ProviderSettings, *, agent_query=None):
        self.config = config
        self.model = config.model or settings.AGENT_MODEL
        self.sdk_version = _sdk_version()
        self._agent_query = agent_query

    def _query(self):
        if self._agent_query is not None:
            return self._agent_query
        from claude_agent_sdk import query

        return query

    async def run(
        self,
        *,
        instructions: str,
        input_text: str,
        workdir: str,
        scenes: list[dict],
        render_engine: str,
        continuation: Any | None,
        is_cancelled: Callable[[], bool],
    ) -> AgentRunResult:
        server, tool_name = build_validate_server(workdir, scenes, render_engine)
        options = self._build_options(server, tool_name, workdir, continuation)
        prompt = input_text if continuation else f"{instructions}\n\n{input_text}"
        session_id = None
        subtype = None
        result_text = ""
        cumulative_cost = 0.0
        cumulative_turns = 0
        tool_calls: list[str] = []
        preview = LiveLLMPreview(
            provider=self.provider,
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )

        stream = self._query()(prompt=prompt, options=options)
        async with contextlib.aclosing(stream) as messages:
            async for message in messages:
                if is_cancelled():
                    logger.info("[ClaudeAgentRuntime] 任务已取消，中断 Agent 循环")
                    raise AgentCancelledError("task cancelled during agent execution")

                for block in getattr(message, "content", []) or []:
                    name = getattr(block, "name", None)
                    if name:
                        tool_calls.append(name)
                        logger.info(
                            "[ClaudeAgentRuntime] 第 %d 次工具调用：%s %s",
                            len(tool_calls),
                            name,
                            _tool_target(block),
                        )
                    else:
                        text = (getattr(block, "text", "") or "").strip()
                        if text:
                            preview.append(text)
                            logger.info(
                                "[ClaudeAgentRuntime] %s",
                                text if len(text) <= 500 else text[:500] + "…",
                            )

                if getattr(message, "session_id", None):
                    session_id = message.session_id
                if _is_result_message(message):
                    subtype = message.subtype
                    result_text = getattr(message, "result", "") or ""
                    cost = getattr(message, "total_cost_usd", None)
                    if cost is not None:
                        cumulative_cost = float(cost)
                    turns = getattr(message, "num_turns", None)
                    if turns:
                        cumulative_turns = int(turns)

        previous_cost = 0.0
        previous_turns = 0
        if isinstance(continuation, dict):
            previous_cost = float(continuation.get("total_cost_usd") or 0)
            previous_turns = int(continuation.get("num_turns") or 0)
        next_continuation = {
            "session_id": session_id,
            "total_cost_usd": cumulative_cost,
            "num_turns": cumulative_turns,
        }
        preview.finish(chunks=1 if result_text else 0, content_len=len(result_text))
        return AgentRunResult(
            status=subtype or "missing_result",
            final_output=result_text,
            continuation=next_continuation,
            total_cost_usd=max(cumulative_cost - previous_cost, 0.0),
            num_turns=max(cumulative_turns - previous_turns, 0),
            tool_calls=tool_calls,
        )

    def _build_options(self, server, tool_name, workdir, continuation):
        from claude_agent_sdk import ClaudeAgentOptions

        env = {"ANTHROPIC_API_KEY": self.config.api_key}
        if self.config.base_url:
            env["ANTHROPIC_BASE_URL"] = self.config.base_url
        kwargs = dict(
            model=self.model,
            cwd=workdir,
            setting_sources=[],
            permission_mode="acceptEdits",
            max_turns=settings.AGENT_MAX_TURNS,
            max_budget_usd=settings.AGENT_MAX_BUDGET_USD,
            mcp_servers={"codegen": server},
            allowed_tools=[*CLAUDE_TOOL_WHITELIST, tool_name],
            tools=list(CLAUDE_TOOL_WHITELIST),
            env=env,
        )
        if isinstance(continuation, dict) and continuation.get("session_id"):
            kwargs["resume"] = continuation["session_id"]
        return ClaudeAgentOptions(**kwargs)
