from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.engines.ai.factory import ProviderSettings
from app.services.strategies.claude_agent_runtime import ClaudeAgentRuntime


def _config():
    return ProviderSettings(
        provider_type="anthropic",
        api_key="sk-test",
        base_url="https://anthropic.example.invalid",
        model="claude-test",
        timeout_seconds=30,
        content_max_tokens=1000,
        json_max_tokens=1000,
        input_cost_per_million=Decimal("1"),
        cached_input_cost_per_million=Decimal("0.5"),
        output_cost_per_million=Decimal("2"),
    )


class FakeResultMessage:
    def __init__(self, *, subtype="success", cost=0.4, turns=3, session_id="sess-1"):
        self.subtype = subtype
        self.result = "done"
        self.total_cost_usd = cost
        self.num_turns = turns
        self.session_id = session_id


def _query(messages, seen):
    async def fake_query(*, prompt, options):
        seen.append((prompt, options))
        for message in messages:
            yield message

    return fake_query


@pytest.mark.asyncio
async def test_claude_runtime_preserves_whitelist_budget_and_resume():
    seen = []
    runtime = ClaudeAgentRuntime(_config(), agent_query=_query([FakeResultMessage(cost=0.9, turns=6)], seen))
    continuation = {"session_id": "old-session", "total_cost_usd": 0.4, "num_turns": 3}

    with patch(
        "app.services.strategies.claude_agent_runtime.build_validate_server",
        return_value=(MagicMock(), "mcp__codegen__validate"),
    ):
        result = await runtime.run(
            instructions="system",
            input_text="repair",
            workdir="C:/tmp/work",
            scenes=[{"scene_index": 0}],
            render_engine="manim",
            continuation=continuation,
            is_cancelled=lambda: False,
        )

    prompt, options = seen[0]
    assert prompt == "repair"
    assert options.tools == ["Read", "Write", "Edit", "Glob"]
    assert "Bash" not in options.allowed_tools
    assert "mcp__codegen__validate" in options.allowed_tools
    assert options.setting_sources == []
    assert options.max_budget_usd
    assert options.resume == "old-session"
    assert options.env["ANTHROPIC_API_KEY"] == "sk-test"
    assert result.total_cost_usd == pytest.approx(0.5)
    assert result.num_turns == 3


@pytest.mark.asyncio
async def test_claude_runtime_marks_missing_result_message_as_failure():
    seen = []

    class SystemMessage:
        subtype = "init"

    runtime = ClaudeAgentRuntime(_config(), agent_query=_query([SystemMessage()], seen))
    with patch(
        "app.services.strategies.claude_agent_runtime.build_validate_server",
        return_value=(MagicMock(), "mcp__codegen__validate"),
    ):
        result = await runtime.run(
            instructions="system",
            input_text="start",
            workdir="C:/tmp/work",
            scenes=[{"scene_index": 0}],
            render_engine="manim",
            continuation=None,
            is_cancelled=lambda: False,
        )

    assert seen[0][0] == "system\n\nstart"
    assert result.status == "missing_result"
