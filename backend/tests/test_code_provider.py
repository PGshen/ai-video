import pytest
from app.engines.ai.chat_provider import ChatAIProvider
from app.engines.ai.stub import StubChatClient
from app.engines.ai.base import CodeGenerationResult

SAMPLE_SCENES = [
    {
        "scene_index": 0,
        "narration": "天空是蓝色的",
        "description": "黑色背景，用 Write 写出标题",
        "estimated_duration_seconds": 5.0,
    },
    {
        "scene_index": 1,
        "narration": "这是因为瑞利散射",
        "description": "承接标题，缩小到顶部，绘制散射图示",
        "estimated_duration_seconds": 7.0,
    },
]


def make_provider():
    return ChatAIProvider(client=StubChatClient())


@pytest.mark.asyncio
async def test_generate_code_returns_code_generation_result():
    provider = make_provider()
    result = await provider.generate_code(scenes=SAMPLE_SCENES, render_engine="manim")
    assert isinstance(result, CodeGenerationResult)
    assert isinstance(result.codes, list)


@pytest.mark.asyncio
async def test_generate_code_stub_returns_empty_list():
    provider = make_provider()
    result = await provider.generate_code(scenes=SAMPLE_SCENES, render_engine="manim")
    # Stub returns empty codes list
    assert result.codes == []


def test_generate_code_prompt_contains_engine_rules():
    """代码生成使用引擎特定规范"""
    manim_prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "construct()" in manim_prompt
