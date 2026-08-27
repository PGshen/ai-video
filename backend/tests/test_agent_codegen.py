import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.services.strategies.agent_codegen import AgentCancelledError, AgentCodegenStrategy
from app.services.strategies.agent_runtime import AgentRunResult

SCENES = [{"scene_index": 0, "narration": "旁白", "description": "描述", "beats": []}]


class FakeRuntime:
    provider = "openai"
    model = "gpt-test"
    sdk_name = "openai-agents"
    sdk_version = "test"

    def __init__(self, results=None, *, delay=0, error=None):
        self.results = list(results or [AgentRunResult(status="success")])
        self.delay = delay
        self.error = error
        self.calls = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.results.pop(0)


def _strategy(runtime):
    return AgentCodegenStrategy(runtime_factory=lambda config: runtime)


def _patch_common(validate, *, codes=("# code",), cancelled=False):
    return (
        patch("app.services.strategies.agent_codegen._agent_provider_config", return_value=MagicMock()),
        patch("app.services.strategies.agent_codegen.validate_workdir", validate),
        patch("app.services.strategies.agent_codegen.read_scene_codes", return_value=list(codes)),
        patch("app.services.strategies.agent_codegen.is_task_cancelled", return_value=cancelled),
        patch("app.services.strategies.agent_codegen.record_agent_call", AsyncMock()),
    )


@pytest.mark.asyncio
async def test_platform_validation_failure_triggers_one_continuation():
    runtime = FakeRuntime(
        [
            AgentRunResult(status="success", continuation={"history": ["first"]}),
            AgentRunResult(status="success"),
        ]
    )
    results = [(False, "scene 0: NameError"), (True, "")]

    async def validate(*args):
        return results.pop(0)

    patches = _patch_common(validate)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        outcome = await _strategy(runtime).run(
            scenes=SCENES,
            render_engine="manim",
            style_components={},
            aspect_ratio="landscape",
            rejection_context=None,
            previous_code_scenes=None,
            task_id="t1",
        )

    assert len(runtime.calls) == 2
    assert runtime.calls[1]["continuation"] == {"history": ["first"]}
    assert outcome.scenes[0]["code"] == "# code"
    assert outcome.trace["resumed"] is True


@pytest.mark.asyncio
async def test_continuation_is_attempted_at_most_once():
    runtime = FakeRuntime(
        [AgentRunResult(status="success"), AgentRunResult(status="success")]
    )

    async def validate(*args):
        return False, "scene 0: SyntaxError"

    patches = _patch_common(validate)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        with pytest.raises(ValueError, match="SyntaxError"):
            await _strategy(runtime).run(
                scenes=SCENES,
                render_engine="manim",
                style_components={},
                aspect_ratio="landscape",
                rejection_context=None,
                previous_code_scenes=None,
                task_id="t1",
            )
    assert len(runtime.calls) == 2


@pytest.mark.asyncio
async def test_non_success_runtime_status_is_a_failure_even_when_validation_passes():
    runtime = FakeRuntime(
        [
            AgentRunResult(status="error_max_turns"),
            AgentRunResult(status="error_max_turns"),
        ]
    )

    async def validate(*args):
        return True, ""

    patches = _patch_common(validate)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        with pytest.raises(ValueError, match="error_max_turns"):
            await _strategy(runtime).run(
                scenes=SCENES,
                render_engine="manim",
                style_components={},
                aspect_ratio="landscape",
                rejection_context=None,
                previous_code_scenes=None,
                task_id="t1",
            )


@pytest.mark.asyncio
async def test_trace_accumulates_provider_usage_cost_and_tools():
    runtime = FakeRuntime(
        [
            AgentRunResult(
                status="success",
                final_output="done",
                usage={"requests": 2, "input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
                total_cost_usd=0.34,
                num_turns=2,
                tool_calls=["read_context_file", "write_scene", "validate"],
            )
        ]
    )

    async def validate(*args):
        return True, ""

    patches = _patch_common(validate)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        outcome = await _strategy(runtime).run(
            scenes=SCENES,
            render_engine="manim",
            style_components={},
            aspect_ratio="landscape",
            rejection_context=None,
            previous_code_scenes=None,
            task_id=None,
        )

    assert outcome.trace["provider"] == "openai"
    assert outcome.trace["sdk_name"] == "openai-agents"
    assert outcome.trace["total_cost_usd"] == 0.34
    assert outcome.trace["num_turns"] == 2
    assert outcome.trace["usage"]["total_tokens"] == 14
    assert outcome.trace["tool_calls"][-1] == "validate"


@pytest.mark.asyncio
async def test_cancellation_aborts_runtime_records_and_cleans_workdir():
    runtime = FakeRuntime(delay=10)
    recorder = AsyncMock()
    captured = {}
    original_run = runtime.run

    async def capture_run(**kwargs):
        captured["workdir"] = kwargs["workdir"]
        return await original_run(**kwargs)

    runtime.run = capture_run
    async def validate(*args):
        return True, ""

    with patch(
        "app.services.strategies.agent_codegen._agent_provider_config", return_value=MagicMock()
    ), patch(
        "app.services.strategies.agent_codegen.validate_workdir", validate
    ), patch(
        "app.services.strategies.agent_codegen.is_task_cancelled", return_value=True
    ), patch(
        "app.services.strategies.agent_codegen.record_agent_call", recorder
    ):
        with pytest.raises(AgentCancelledError):
            await _strategy(runtime).run(
                scenes=SCENES,
                render_engine="manim",
                style_components={},
                aspect_ratio="landscape",
                rejection_context=None,
                previous_code_scenes=None,
                task_id="t1",
            )

    assert recorder.await_args.kwargs["status"] == "cancelled"
    assert not os.path.exists(captured["workdir"])


@pytest.mark.asyncio
async def test_wall_clock_timeout_aborts_the_run():
    runtime = FakeRuntime(delay=10)

    async def validate(*args):
        return True, ""

    patches = _patch_common(validate)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patch.object(
        settings, "AGENT_TIMEOUT_SECONDS", 0.05
    ):
        with pytest.raises(ValueError, match="超时"):
            await _strategy(runtime).run(
                scenes=SCENES,
                render_engine="manim",
                style_components={},
                aspect_ratio="landscape",
                rejection_context=None,
                previous_code_scenes=None,
                task_id="t1",
            )


def test_agent_provider_config_accepts_openai_and_rejects_other_providers():
    from app.services.strategies.agent_codegen import _agent_provider_config

    openai_config = MagicMock(provider_type="openai")
    with patch("app.engines.ai.factory._provider_settings_from_db", return_value=openai_config):
        assert _agent_provider_config() is openai_config

    bad_config = MagicMock(provider_type="deepseek")
    with patch("app.engines.ai.factory._provider_settings_from_db", return_value=bad_config):
        with pytest.raises(ValueError, match="anthropic 或 openai"):
            _agent_provider_config()


@pytest.mark.asyncio
async def test_non_manim_render_engine_is_rejected_before_config_lookup():
    runtime = FakeRuntime()
    with patch("app.services.strategies.agent_codegen._agent_provider_config") as config:
        with pytest.raises(ValueError, match="manim"):
            await _strategy(runtime).run(
                scenes=SCENES,
                render_engine="remotion",
                style_components={},
                aspect_ratio="landscape",
                rejection_context=None,
                previous_code_scenes=None,
                task_id="t1",
            )
    config.assert_not_called()
