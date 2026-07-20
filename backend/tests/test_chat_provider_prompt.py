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
        # 引擎叙事规范只描述能力与语义约束；配色由平台 color_scheme 注入
        assert "#6C4FD4" not in prompt
        assert "#FF6B6B" not in prompt
        assert "#4ECDC4" not in prompt
        assert "关键公式" in prompt
        assert "cue_text" in prompt
        assert "visual_action" in prompt

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


def test_remotion_prompt_uses_tailwind_only_for_static_styles():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["remotion"]
    assert "静态 Tailwind + 动态内联样式" in prompt
    assert "scene-title" in prompt
    assert "禁止动态拼接 Tailwind 类名" in prompt
    assert "animate-*" in prompt
    assert "逐帧动态值" in prompt


def test_prompts_contain_semantic_beat_contracts():
    provider = make_provider()
    narrative_prompt = provider._build_narrative_system_prompt("manim", {})
    code_prompt = provider._build_code_system_prompt("manim", {})

    assert "【语义节拍契约】" in narrative_prompt
    assert "cue_text 必须逐字取自 narration" in narrative_prompt
    assert "beat_index 在每个 scene 内必须从 0 连续递增" in narrative_prompt
    assert "transition 只能是 continue、transform、reveal、replace、exit 之一" in narrative_prompt
    assert "不输出绝对时间" in narrative_prompt
    assert "【语义节拍时间执行契约】" in code_prompt
    assert "不得在第一个 beat 中一次性完成" in code_prompt
    assert "animation_start_seconds" in ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "startFrame" in ChatAIProvider._ENGINE_CODE_PROMPTS["remotion"]


def test_portrait_prompts_use_mobile_composition_and_dimensions():
    provider = make_provider()
    narrative_prompt = provider._build_narrative_system_prompt(
        "manim", {}, aspect_ratio="portrait"
    )
    code_prompt = provider._build_code_system_prompt(
        "remotion", {}, aspect_ratio="portrait"
    )

    assert "竖屏 9:16（手机端）" in narrative_prompt
    assert "1080 × 1920 px" in narrative_prompt
    assert "自上而下的纵向视觉动线" in narrative_prompt
    assert "安全区 x ∈ [-1.9, 1.9]" in narrative_prompt
    assert "width=1080、height=1920" in code_prompt
    assert "不得沿用固定横屏坐标" in code_prompt


def test_landscape_prompt_remains_default():
    prompt = make_provider()._build_code_system_prompt("manim", {})

    assert "横屏 16:9" in prompt
    assert "1920 × 1080 px" in prompt


def test_system_prompt_contains_visual_first_rule():
    """generate_code 的 system prompt 应包含视觉优先要求"""
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
    # 配色系统已移至 style_components（DB prompt_components），不再硬编码在 YAML code_prompt 中
    # 此测试改为验证 YAML 中不再重复包含这些颜色（避免双重注入）
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "#E8524A" not in prompt   # 草莓红应由 style_component 注入
    assert "#F07D3E" not in prompt   # 橘橙应由 style_component 注入


def test_manim_code_prompt_animation_rhythm():
    # 动画节奏规范已移至 style_components，不再硬编码在 YAML code_prompt 中
    # 此测试改为验证 YAML 保留引擎技术约束（GrowArrow 禁用说明仍在禁用类名列表）
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "GrowArrow" in prompt   # 禁用类名列表中仍提及 GrowArrow
    assert "GrowFromCenter" not in prompt  # 动画风格建议应由 style_component 注入


def test_manim_code_prompt_exit_checklist():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "画布存量" in prompt
    assert "镜头开头" in prompt or "开头" in prompt
    assert "run_time=0.5" in prompt


def test_remotion_code_prompt_warm_colors():
    # 配色系统已移至 style_components，不再硬编码在 YAML code_prompt 中
    # 此测试改为验证 YAML 中不再重复包含这些颜色（避免双重注入）
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["remotion"]
    assert "#E8524A" not in prompt   # 草莓红应由 style_component 注入
    assert "#2C2C2C" not in prompt   # 深炭灰应由 style_component 注入


def test_remotion_code_prompt_canvas_size():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["remotion"]
    assert "1280" in prompt or "720" in prompt or "canvas" in prompt.lower() or "画布" in prompt


def test_narrative_prompt_uses_style_exemplar_as_format_example():
    provider = make_provider()
    prompt = provider._build_narrative_system_prompt(
        "manim",
        {
            "narrative_style": "【叙事蓝图】测试蓝图",
            "exemplar": '{"scenes": [{"narration": "范例旁白语感"}]}',
        },
    )
    assert "范例旁白语感" in prompt
    assert "【输出格式与风格范例】" in prompt
    # 内置通用示例被顶替
    assert "责任几乎全部落在你身上" not in prompt
    assert "【叙事蓝图】测试蓝图" in prompt


def test_narrative_prompt_falls_back_to_builtin_exemplar():
    provider = make_provider()
    prompt = provider._build_narrative_system_prompt("manim", {})
    assert "责任几乎全部落在你身上" in prompt
    assert "scene_index" in prompt


def test_narrative_prompt_new_style_has_no_default_pacing_leak():
    """未提供额外类别时，不得注入旧系统默认文本。"""
    provider = make_provider()
    prompt = provider._build_narrative_system_prompt(
        "manim", {"narrative_style": "【叙事蓝图】完整蓝图"}
    )
    assert "15-20 个镜头" not in prompt
