import pytest
from unittest.mock import AsyncMock, MagicMock
from app.engines.ai.chat_provider import ChatAIProvider


def make_provider(response_json: str) -> ChatAIProvider:
    client = MagicMock()
    client.engine_name = "test"
    client.model_name = "test-model"
    client.create_chat_completion = AsyncMock(return_value=response_json)
    return ChatAIProvider(client=client)


VALID_SCRIPT_JSON = '''{
  "scenes": [
    {
      "scene_index": 0,
      "narration": "旁白",
      "description": "画面",
      "code": "class S(Scene): pass",
      "estimated_duration_seconds": 5.0
    }
  ],
  "fact_checks": [
    {
      "claim_text": "论断",
      "scene_index": 0,
      "source_url": null,
      "source_description": "来源",
      "confidence": "medium",
      "is_hypothesis": false,
      "assumptions": null,
      "controversy": null,
      "reviewer_verdict": null,
      "reviewer_note": null
    }
  ]
}'''


@pytest.mark.asyncio
async def test_generate_script_manim_prompt_contains_engine_hint():
    provider = make_provider(VALID_SCRIPT_JSON)
    await provider.generate_script(
        topic_title="测试选题",
        topic_description="描述",
        render_engine="manim",
    )
    call_args = provider.client.create_chat_completion.call_args
    messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
    system_content = messages[0]["content"]
    assert "Manim" in system_content or "manim" in system_content
    assert "Scene" in system_content


@pytest.mark.asyncio
async def test_generate_script_remotion_prompt_contains_engine_hint():
    provider = make_provider(VALID_SCRIPT_JSON)
    await provider.generate_script(
        topic_title="测试选题",
        topic_description="描述",
        render_engine="remotion",
    )
    call_args = provider.client.create_chat_completion.call_args
    messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
    system_content = messages[0]["content"]
    assert "Remotion" in system_content or "remotion" in system_content


@pytest.mark.asyncio
async def test_generate_script_unknown_engine_uses_fallback():
    """未知引擎不应抛异常，走通用 prompt"""
    provider = make_provider(VALID_SCRIPT_JSON)
    result = await provider.generate_script(
        topic_title="测试选题",
        topic_description="描述",
        render_engine="unknown_engine",
    )
    assert len(result.scenes) == 1
    assert len(result.fact_checks) == 1


@pytest.mark.asyncio
async def test_generate_script_with_rejection_context():
    """驳回重生成时，rejection_context 应出现在 user message 中"""
    provider = make_provider(VALID_SCRIPT_JSON)
    rejection_context = {"rejection_type": "fact_error", "rejection_detail": "第1条事实有误"}
    await provider.generate_script(
        topic_title="测试选题",
        topic_description="描述",
        render_engine="manim",
        rejection_context=rejection_context,
    )
    call_args = provider.client.create_chat_completion.call_args
    messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
    user_content = messages[-1]["content"]
    assert "fact_error" in user_content or "rejection" in user_content.lower()
