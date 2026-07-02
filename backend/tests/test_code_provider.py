import pytest
import json
from unittest.mock import AsyncMock
from app.engines.ai.chat_provider import ChatAIProvider
from app.engines.ai.stub import StubChatClient
from app.engines.ai.base import CodeGenerationResult, CodeRepairResult

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
async def test_generate_code_stub_returns_one_code_per_scene():
    provider = make_provider()
    result = await provider.generate_code(scenes=SAMPLE_SCENES, render_engine="manim")
    assert result.codes == ["# stub generated code", "# stub generated code"]


def test_generate_code_prompt_contains_engine_rules():
    """代码生成使用引擎特定规范"""
    manim_prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "construct()" in manim_prompt


@pytest.mark.asyncio
async def test_repair_code_checks_all_scenes_and_returns_targeted_repairs():
    client = StubChatClient()
    client.create_chat_completion = AsyncMock(return_value=json.dumps({
        "repairs": [{
            "scene_index": 1,
            "code": "fixed = Text('修复')",
            "explanation": "移除了不支持的参数",
        }],
    }))
    provider = ChatAIProvider(client=client)
    scenes = [
        {**scene, "code": f"code {scene['scene_index']}"}
        for scene in SAMPLE_SCENES
    ]

    result = await provider.repair_code(
        scenes=scenes,
        render_engine="manim",
        error_message="unexpected keyword argument 'label'",
    )

    assert isinstance(result, CodeRepairResult)
    assert result.repairs[0]["scene_index"] == 1
    messages = client.create_chat_completion.await_args.kwargs["messages"]
    assert "全部可能有错误的镜头" in messages[0]["content"]
    assert "unexpected keyword argument" in messages[1]["content"]
    assert '"scene_index": 0' in messages[1]["content"]
    assert '"scene_index": 1' in messages[1]["content"]


@pytest.mark.asyncio
async def test_repair_code_rejects_unknown_scene_index():
    client = StubChatClient()
    client.create_chat_completion = AsyncMock(return_value=json.dumps({
        "repairs": [{
            "scene_index": 99,
            "code": "fixed = True",
            "explanation": "错误镜头",
        }],
    }))
    provider = ChatAIProvider(client=client)

    with pytest.raises(ValueError, match="Invalid code repair item"):
        await provider.repair_code(
            scenes=[{**SAMPLE_SCENES[0], "code": "broken"}],
            render_engine="manim",
            error_message="render failed",
        )
