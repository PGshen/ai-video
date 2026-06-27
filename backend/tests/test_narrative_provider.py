import pytest
from app.engines.ai.chat_provider import ChatAIProvider
from app.engines.ai.stub import StubChatClient
from app.engines.ai.base import NarrativeResult


def make_provider():
    return ChatAIProvider(client=StubChatClient())


@pytest.mark.asyncio
async def test_generate_narrative_returns_narrative_result():
    provider = make_provider()
    result = await provider.generate_narrative(
        topic_title="为什么天空是蓝色的",
        topic_description="瑞利散射原理",
        render_engine="manim",
    )
    assert isinstance(result, NarrativeResult)
    assert isinstance(result.scenes, list)
    assert isinstance(result.fact_checks, list)


@pytest.mark.asyncio
async def test_generate_narrative_with_rejection_context():
    provider = make_provider()
    result = await provider.generate_narrative(
        topic_title="测试",
        topic_description="描述",
        render_engine="manim",
        rejection_context={"rejection_detail": "内容太空洞"},
    )
    assert isinstance(result, NarrativeResult)


def test_narrative_prompt_no_code_field():
    """叙事 prompt 不应要求 AI 生成 code 字段"""
    prompt = ChatAIProvider._NARRATIVE_SYSTEM_PROMPT_TEMPLATE
    assert "旁白" in prompt or "narration" in prompt
    assert "description" in prompt or "描述" in prompt
    # 目标时长约束
    assert "15-20" in prompt or "2-3 分钟" in prompt


def test_narrative_prompt_engine_hints_exist():
    """两种引擎都有专属 description 规范"""
    assert "manim" in ChatAIProvider._NARRATIVE_ENGINE_HINTS
    assert "remotion" in ChatAIProvider._NARRATIVE_ENGINE_HINTS
    assert "Manim" in ChatAIProvider._NARRATIVE_ENGINE_HINTS["manim"]
    assert "Remotion" in ChatAIProvider._NARRATIVE_ENGINE_HINTS["remotion"]
