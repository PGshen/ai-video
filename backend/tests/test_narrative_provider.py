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
    prompt = ChatAIProvider._NARRATIVE_SYSTEM_PROMPT
    assert "code" not in prompt.lower().replace("渲染代码", "").replace("code_generating", "")
    assert "旁白" in prompt or "narration" in prompt
    assert "description" in prompt or "描述" in prompt
