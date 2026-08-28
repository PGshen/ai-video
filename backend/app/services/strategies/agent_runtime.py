from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from app.engines.ai.factory import ProviderSettings


class AgentCancelledError(Exception):
    """任务在 Agent 执行途中被取消。"""


@dataclass
class AgentRunResult:
    """一次 SDK run 的供应商无关结果。

    usage、total_cost_usd 和 num_turns 均为本次 run 的增量；平台层负责在续跑时累加。
    """

    status: str
    final_output: str = ""
    continuation: Any | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    total_cost_usd: float | None = None
    num_turns: int = 0
    tool_calls: list[str] = field(default_factory=list)


class AgentRuntime(Protocol):
    provider: str
    model: str
    sdk_name: str
    sdk_version: str | None

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
    ) -> AgentRunResult: ...


def build_agent_runtime(
    config: ProviderSettings,
    *,
    claude_query=None,
    openai_runner=None,
) -> AgentRuntime:
    provider = config.provider_type.lower()
    if provider == "anthropic":
        from app.services.strategies.claude_agent_runtime import ClaudeAgentRuntime

        return ClaudeAgentRuntime(config, agent_query=claude_query)
    if provider == "openai":
        from app.services.strategies.openai_agent_runtime import OpenAIAgentRuntime

        return OpenAIAgentRuntime(config, runner_run=openai_runner)
    raise ValueError(
        "Agent 模式仅支持 anthropic 或 openai provider，"
        f"当前为 {config.provider_type}"
    )
