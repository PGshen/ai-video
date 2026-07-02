import pytest
import json
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
        return (
            '{"scenes":[{"scene_index":0,"narration":"旁白",'
            '"description":"画面","beats":[{"beat_index":0,'
            '"cue_text":"旁白","visual_action":"文字出现"}]}],'
            '"fact_checks":[]}'
        )

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


@pytest.mark.asyncio
async def test_generate_narrative_sends_all_validation_errors_back_for_correction():
    invalid_response = {
        "scenes": [
            {
                "scene_index": 0,
                "narration": "第一幕",
                "description": "画面一",
                "beats": [{
                    "cue_text": "第一幕",
                    "visual_action": "文字出现",
                    "transition": "fade",
                }],
            },
            {
                "scene_index": 1,
                "narration": "第二幕",
                "description": "画面二",
                "beats": [{
                    "cue_text": "错误文本",
                    "visual_action": "文字变化",
                    "transition": "continue",
                }],
            },
        ],
        "fact_checks": [],
    }
    corrected_response = {
        "scenes": [
            {
                "scene_index": 0,
                "narration": "第一幕",
                "description": "画面一",
                "beats": [{
                    "cue_text": "第一幕",
                    "visual_action": "文字出现",
                    "transition": "reveal",
                }],
            },
            {
                "scene_index": 1,
                "narration": "第二幕",
                "description": "画面二",
                "beats": [{
                    "cue_text": "第二幕",
                    "visual_action": "文字变化",
                    "transition": "continue",
                }],
            },
        ],
        "fact_checks": [],
    }
    responses = iter([
        json.dumps(invalid_response, ensure_ascii=False),
        json.dumps(corrected_response, ensure_ascii=False),
    ])
    calls = []

    class RepairingClient:
        engine_name = "test"
        model_name = "test-model"

        async def create_chat_completion(self, messages, **kwargs):
            calls.append([dict(message) for message in messages])
            return next(responses)

    provider = ChatAIProvider(client=RepairingClient())
    result = await provider.generate_narrative(
        topic_title="测试",
        topic_description="描述",
        render_engine="manim",
    )

    assert len(result.scenes) == 2
    assert len(calls) == 2
    correction_messages = calls[1]
    assert correction_messages[-2] == {
        "role": "assistant",
        "content": json.dumps(invalid_response, ensure_ascii=False),
    }
    correction_prompt = correction_messages[-1]["content"]
    assert "Scene 0 beat 0 has invalid transition" in correction_prompt
    assert "Scene 1 cue_text values must cover narration exactly" in correction_prompt
