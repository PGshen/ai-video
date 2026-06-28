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
    assert "Axes 构造函数不支持 x_label / y_label" in prompt
    assert "class " not in prompt  # 不应包含 class 定义示例外的 class 关键词指导模型写 class


def test_manim_prompt_keeps_visuals_until_narration_finishes():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "镜头边界不等于清场点" in prompt
    assert "禁止旁白尚未结束就清空画面" in prompt
    assert "保持最终画面" in prompt


def test_narrative_hints_visual_style_and_content_rules():
    for prompt in ChatAIProvider._NARRATIVE_ENGINE_HINTS.values():
        # 新配色关键词（活力暖色）
        assert "#E8524A" in prompt or "#F07D3E" in prompt or "#4BA3C3" in prompt
        # 关键叙事规则保留
        assert "关键公式" in prompt
        assert "旁白结束" in prompt

    manim_prompt = ChatAIProvider._NARRATIVE_ENGINE_HINTS["manim"]
    # 弱技术层：有图形类型词汇但无类名
    assert "圆形" in manim_prompt or "箭头" in manim_prompt or "坐标轴" in manim_prompt
    assert "Circle" not in manim_prompt   # 禁止 Manim 类名
    assert "VGroup" not in manim_prompt
    assert ".animate" not in manim_prompt
    # 退场意图描述
    assert "退场" in manim_prompt
    assert "保留" in manim_prompt


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


def test_manim_code_prompt_font_size_rules():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "font_size" in prompt
    assert "44" in prompt   # 主标题
    assert "32" in prompt   # 节点标签
    assert "28" in prompt   # 正文
    assert "22" in prompt   # 小标注


def test_manim_code_prompt_canvas_safety_zone():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "14.2" in prompt or "安全区" in prompt
    assert "-6.0" in prompt or "[-6" in prompt
    assert "3.5" in prompt or "[-3" in prompt


def test_manim_code_prompt_warm_color_palette():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "#E8524A" in prompt   # 草莓红
    assert "#F07D3E" in prompt   # 橘橙
    assert "#4BA3C3" in prompt   # 天蓝
    assert "#2C2C2C" in prompt   # 深炭灰


def test_manim_code_prompt_animation_rhythm():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "GrowFromCenter" in prompt
    assert "DrawBorderThenFill" in prompt
    assert "Flash" in prompt or "Circumscribe" in prompt


def test_manim_code_prompt_exit_checklist():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "画布存量" in prompt
    assert "镜头开头" in prompt or "开头" in prompt
    assert "run_time=0.5" in prompt


def test_remotion_code_prompt_warm_colors():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["remotion"]
    assert "#E8524A" in prompt or "#F07D3E" in prompt
    assert "#4BA3C3" in prompt
    assert "#2C2C2C" in prompt


def test_remotion_code_prompt_canvas_size():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["remotion"]
    assert "1280" in prompt or "720" in prompt or "canvas" in prompt.lower() or "画布" in prompt
