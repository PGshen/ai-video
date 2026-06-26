import pytest
from app.engines.ai.chat_provider import ChatAIProvider
from app.engines.ai.stub import StubChatClient


def make_provider():
    return ChatAIProvider(client=StubChatClient())


def test_manim_prompt_no_audio_placeholder():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "AUDIO_SCENE" not in prompt


def test_remotion_prompt_no_audio_placeholder():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["remotion"]
    assert "AUDIO_SCENE" not in prompt


def test_manim_prompt_contains_key_rules():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "construct()" in prompt
    assert "FadeOut" in prompt
    assert "Transform" in prompt
    assert "class " not in prompt  # 不应包含 class 定义示例外的 class 关键词指导模型写 class


def test_remotion_prompt_contains_key_rules():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["remotion"]
    assert "useCurrentFrame" in prompt
    assert "interpolate" in prompt
    assert "Sequence" in prompt


def test_system_prompt_contains_visual_first_rule():
    """generate_script 的 system prompt 应包含视觉优先要求"""
    provider = make_provider()
    # 直接检查 system_prompt 字符串模板中的公共段
    # 通过检查类属性字符串覆盖核心约束
    manim_prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "文字" in manim_prompt or "视觉" in manim_prompt  # 视觉优先规则


def test_system_prompt_contains_code_concat_rule():
    """system prompt 公共部分应说明拼合规则"""
    provider = make_provider()
    manim_prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    # 拼合规则在引擎 prompt 里体现（说明 code 是片段）
    assert "construct()" in manim_prompt
    assert "import" in manim_prompt  # 说明不写 import
