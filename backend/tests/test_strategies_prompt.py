import pytest
from unittest.mock import AsyncMock, patch

from app.engines.ai.base import CodeGenerationResult
from app.services.strategies import get_codegen_strategy, get_narrative_strategy
from app.services.strategies.prompt_codegen import PromptCodegenStrategy
from app.services.strategies.prompt_narrative import PromptNarrativeStrategy


def test_selector_returns_prompt_strategy_by_default():
    assert isinstance(get_codegen_strategy("prompt"), PromptCodegenStrategy)
    assert isinstance(get_narrative_strategy("prompt"), PromptNarrativeStrategy)


@pytest.mark.asyncio
async def test_prompt_codegen_merges_codes_into_scenes():
    scenes = [
        {"scene_index": 0, "narration": "旁白", "description": "描述", "beats": []},
    ]
    mock_provider = AsyncMock()
    mock_provider.model_name = "stub-model"
    mock_provider.generate_code = AsyncMock(
        return_value=CodeGenerationResult(codes=["# code 0"])
    )
    mock_engine = AsyncMock()
    mock_engine.validate_code = AsyncMock(return_value=(True, ""))

    with patch(
        "app.services.strategies.prompt_codegen.get_ai_provider",
        return_value=mock_provider,
    ), patch(
        "app.services.strategies.prompt_codegen.get_render_engine",
        return_value=mock_engine,
    ):
        outcome = await get_codegen_strategy("prompt").run(
            scenes=scenes,
            render_engine="manim",
            style_components={},
            aspect_ratio="landscape",
            rejection_context=None,
            previous_code_scenes=None,
            task_id="t1",
        )

    assert outcome.scenes[0]["code"] == "# code 0"
    assert outcome.ai_model == "stub-model"
    assert outcome.trace["execution_mode"] == "prompt"
    assert outcome.trace["repair_rounds"] == 0


def test_selector_returns_agent_strategy_for_agent_mode():
    from app.services.strategies.agent_codegen import AgentCodegenStrategy

    assert isinstance(get_codegen_strategy("agent"), AgentCodegenStrategy)


def test_selector_falls_back_to_prompt_for_unknown_mode():
    assert isinstance(get_codegen_strategy("bogus"), PromptCodegenStrategy)
    assert isinstance(get_narrative_strategy("bogus"), PromptNarrativeStrategy)
