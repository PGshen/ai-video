from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from agents.exceptions import MaxTurnsExceeded
from agents.usage import Usage

from app.engines.ai.factory import ProviderSettings
from app.services.strategies.openai_agent_runtime import (
    OpenAIBudgetExceededError,
    OpenAIAgentRuntime,
    OpenAICodegenWorkspace,
    _build_budget_hooks,
    _cost_from_usage,
    build_openai_tools,
)
from app.config import settings


def _config(**overrides):
    values = dict(
        provider_type="openai",
        api_key="sk-test",
        base_url="https://openai.example.invalid/v1",
        model="gpt-test",
        timeout_seconds=30,
        content_max_tokens=1000,
        json_max_tokens=1000,
        input_cost_per_million=Decimal("1"),
        cached_input_cost_per_million=Decimal("0.5"),
        output_cost_per_million=Decimal("2"),
    )
    values.update(overrides)
    return ProviderSettings(**values)


def _workspace(tmp_path):
    (tmp_path / "scenes").mkdir()
    (tmp_path / "input.json").write_text("{}", encoding="utf-8")
    (tmp_path / "STYLE.md").write_text("style", encoding="utf-8")
    return OpenAICodegenWorkspace(
        str(tmp_path), [{"scene_index": 0}], "manim", lambda: False
    )


def test_workspace_only_exposes_bounded_scene_operations(tmp_path):
    workspace = _workspace(tmp_path)
    assert workspace.read_context_file("input.json") == "{}"
    assert workspace.write_scene(0, "self.wait(1)").startswith("已写入")
    assert workspace.read_scene(0) == "self.wait(1)"
    assert workspace.edit_scene(0, "wait(1)", "wait(2)").startswith("已更新")
    assert workspace.read_scene(0) == "self.wait(2)"
    assert "scene_00.py" in workspace.list_scene_files()
    with pytest.raises(ValueError, match="超出范围"):
        workspace.write_scene(1, "bad")
    with pytest.raises(ValueError, match="精确匹配一次"):
        workspace.edit_scene(0, "missing", "replacement")


@pytest.mark.asyncio
async def test_workspace_validate_reuses_platform_validator(tmp_path):
    workspace = _workspace(tmp_path)
    with patch(
        "app.services.strategies.openai_agent_runtime.validate_workdir",
        return_value=(False, "scene 0: error"),
    ) as validator:
        result = await workspace.validate()
    assert result == "校验失败：\nscene 0: error"
    validator.assert_awaited_once()


def test_openai_tool_surface_has_no_shell_or_arbitrary_path_tool(tmp_path):
    tools = build_openai_tools(_workspace(tmp_path))
    names = {tool.name for tool in tools}
    assert names == {
        "read_context_file",
        "list_scene_files",
        "read_scene",
        "write_scene",
        "edit_scene",
        "validate",
    }


def test_openai_runtime_requires_pricing_for_budget_enforcement():
    with pytest.raises(ValueError, match="输入和输出单价"):
        OpenAIAgentRuntime(_config(input_cost_per_million=Decimal("0")))
    with pytest.raises(ValueError, match="输入和输出单价"):
        OpenAIAgentRuntime(_config(output_cost_per_million=Decimal("0")))


def test_openai_cost_uses_input_price_when_cached_price_is_not_configured():
    cost = _cost_from_usage(
        {
            "input_tokens": 100,
            "output_tokens": 0,
            "input_tokens_details": {"cached_tokens": 100},
        },
        _config(cached_input_cost_per_million=Decimal("0")),
    )

    assert cost == pytest.approx(0.0001)


@pytest.mark.asyncio
async def test_openai_budget_hook_blocks_before_an_over_budget_continuation():
    hooks = _build_budget_hooks(_config(), previous_cost_usd=0.2)

    with patch.object(settings, "AGENT_MAX_BUDGET_USD", 0.2):
        with pytest.raises(OpenAIBudgetExceededError) as exc_info:
            await hooks.on_llm_start(SimpleNamespace(), None, None, [])

    assert exc_info.value.total_cost_usd == 0.2


@pytest.mark.asyncio
async def test_openai_budget_hook_prices_cumulative_usage_after_model_call():
    hooks = _build_budget_hooks(_config(), previous_cost_usd=0.1)
    context = SimpleNamespace(
        usage=Usage(requests=1, input_tokens=100, output_tokens=20, total_tokens=120)
    )

    with patch.object(settings, "AGENT_MAX_BUDGET_USD", 0.1001):
        with pytest.raises(OpenAIBudgetExceededError) as exc_info:
            await hooks.on_llm_end(context, None, None)

    assert exc_info.value.total_cost_usd == pytest.approx(0.10014)
    assert exc_info.value.usage["total_tokens"] == 120


@pytest.mark.asyncio
async def test_openai_runtime_uses_runner_history_usage_and_disabled_tracing(tmp_path):
    workspace = _workspace(tmp_path)
    del workspace  # runtime creates its own wrapper around the prepared directory
    seen = []
    usage = Usage(requests=2, input_tokens=100, output_tokens=20, total_tokens=120)
    history = [{"role": "assistant", "content": "done"}]

    async def fake_runner(agent, run_input, **kwargs):
        seen.append((agent, run_input, kwargs))
        return SimpleNamespace(
            final_output="done",
            context_wrapper=SimpleNamespace(usage=usage),
            to_input_list=lambda: history,
        )

    runtime = OpenAIAgentRuntime(_config(), runner_run=fake_runner)
    result = await runtime.run(
        instructions="system",
        input_text="start",
        workdir=str(tmp_path),
        scenes=[{"scene_index": 0}],
        render_engine="manim",
        continuation=None,
        is_cancelled=lambda: False,
    )

    agent, run_input, kwargs = seen[0]
    assert run_input == "start"
    assert agent.model.model == "gpt-test"
    assert agent.model._client.api_key == "sk-test"
    assert agent.model_settings.parallel_tool_calls is False
    assert kwargs["run_config"].tracing_disabled is True
    assert result.status == "success"
    assert result.continuation["history"] == history
    assert result.usage["requests"] == 2
    assert result.total_cost_usd == pytest.approx(0.00014)


@pytest.mark.asyncio
async def test_openai_runtime_appends_repair_input_to_history(tmp_path):
    _workspace(tmp_path)
    seen = []

    async def fake_runner(agent, run_input, **kwargs):
        seen.append(run_input)
        return SimpleNamespace(
            final_output="fixed",
            context_wrapper=SimpleNamespace(usage=Usage()),
            to_input_list=lambda: [],
        )

    runtime = OpenAIAgentRuntime(_config(), runner_run=fake_runner)
    await runtime.run(
        instructions="system",
        input_text="repair",
        workdir=str(tmp_path),
        scenes=[{"scene_index": 0}],
        render_engine="manim",
        continuation={"history": [{"role": "assistant", "content": "old"}], "spent_usd": 0.2},
        is_cancelled=lambda: False,
    )
    assert seen[0][-1] == {"role": "user", "content": "repair"}


@pytest.mark.asyncio
async def test_openai_max_turns_becomes_runtime_status(tmp_path):
    _workspace(tmp_path)

    async def fake_runner(*args, **kwargs):
        raise MaxTurnsExceeded("max turns")

    result = await OpenAIAgentRuntime(_config(), runner_run=fake_runner).run(
        instructions="system",
        input_text="start",
        workdir=str(tmp_path),
        scenes=[{"scene_index": 0}],
        render_engine="manim",
        continuation=None,
        is_cancelled=lambda: False,
    )
    assert result.status == "error_max_turns"
