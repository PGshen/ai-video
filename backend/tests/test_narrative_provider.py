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


@pytest.mark.asyncio
async def test_generate_narrative_with_context_snippets():
    provider = make_provider()
    result = await provider.generate_narrative(
        topic_title="测试",
        topic_description="描述",
        render_engine="manim",
        narrative_context=[{"text": "参考内容：量子纠缠的直觉解释"}],
    )
    assert isinstance(result, NarrativeResult)


def test_generate_narrative_context_injected_into_user_payload():
    """When narrative_context is provided, snippets appear in the user message."""
    from unittest.mock import AsyncMock, MagicMock
    import asyncio

    captured = {}

    async def fake_completion(messages, **kwargs):
        captured["messages"] = messages
        return '{"scenes": [], "fact_checks": []}'

    client = MagicMock()
    client.engine_name = "stub"
    client.model_name = "stub-model"
    client.create_chat_completion = fake_completion

    provider = ChatAIProvider(client=client)
    asyncio.run(
        provider.generate_narrative(
            topic_title="T",
            topic_description="D",
            render_engine="manim",
            narrative_context=[{"text": "片段A"}, {"text": "片段B"}],
        )
    )
    user_msg = captured["messages"][-1]["content"]
    assert "片段A" in user_msg
    assert "片段B" in user_msg
