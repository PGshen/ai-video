import ast

from app.engines.render.base import SceneInput
from app.engines.render.manim import (
    ManimRenderEngine,
    _build_manim_script,
    _prepare_manim_code,
)


def test_prepare_manim_code_injects_template_into_formula_calls():
    code = """
formula = MathTex(r"\\text{面积}=\\pi r^2")
caption = Tex("中文说明")
label = Text("普通中文")
"""

    prepared, changed = _prepare_manim_code(code)
    tree = ast.parse(prepared)
    calls = {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert changed is True
    assert any(keyword.arg == "tex_template" for keyword in calls["MathTex"].keywords)
    assert any(keyword.arg == "tex_template" for keyword in calls["Tex"].keywords)
    assert not any(keyword.arg == "tex_template" for keyword in calls["Text"].keywords)


def test_prepare_manim_code_preserves_explicit_template():
    code = 'formula = MathTex("x", tex_template=custom_template)'

    prepared, changed = _prepare_manim_code(code)

    assert changed is False
    assert prepared == code


def test_prepare_manim_code_supports_qualified_constructor():
    prepared, changed = _prepare_manim_code('formula = manim.MathTex("x")')

    assert changed is True
    assert "tex_template=_chinese_tex_template" in prepared


def test_prepare_manim_code_injects_template_into_chinese_bulleted_list():
    code = """
bullets = BulletedList(
    "主观时间加速",
    "童年慢于成年",
    "中点提前",
)
"""

    prepared, changed = _prepare_manim_code(code)
    tree = ast.parse(prepared)
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "BulletedList"
    )

    assert changed is True
    assert any(keyword.arg == "tex_template" for keyword in call.keywords)


def test_prepare_manim_code_repairs_double_escaped_latex_commands():
    code = r"""
formula = MathTex(
    r'\\frac{\\Delta t_{心理}}{\\Delta t_{物理}} = \\frac{1}{年龄+1}'
)
"""

    prepared, changed = _prepare_manim_code(code)
    tree = ast.parse(prepared)
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "MathTex"
    )

    assert changed is True
    assert call.args[0].value == (
        r"\frac{\Delta t_{心理}}{\Delta t_{物理}} = \frac{1}{年龄+1}"
    )


def test_prepare_manim_code_preserves_latex_line_breaks():
    code = r"""
formula = MathTex(r"\begin{aligned}x &= 1 \\ y &= 2\end{aligned}")
"""

    prepared, _ = _prepare_manim_code(code)
    tree = ast.parse(prepared)
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "MathTex"
    )

    assert call.args[0].value == r"\begin{aligned}x &= 1 \\ y &= 2\end{aligned}"


def test_build_manim_script_adds_xelatex_ctex_template():
    scene = SceneInput(
        scene_index=0,
        narration="圆的面积",
        description="展示中文公式",
        code='formula = MathTex(r"\\text{面积}=\\pi r^2")',
        audio=None,
    )

    script = _build_manim_script([scene])

    assert 'TexTemplate(tex_compiler="xelatex", output_format=".xdv")' in script
    assert r"\usepackage[UTF8,fontset=fandol]{ctex}" in script
    assert "tex_template=_chinese_tex_template" in script


def test_build_manim_script_skips_template_without_tex_calls():
    scene = SceneInput(
        scene_index=0,
        narration="标题",
        description="普通文字",
        code='title = Text("中文标题")',
        audio=None,
    )

    script = _build_manim_script([scene])

    assert "_chinese_tex_template" not in script


def test_build_manim_script_sets_portrait_pixel_and_logical_canvas():
    scene = SceneInput(
        scene_index=0,
        narration="标题",
        description="竖屏标题",
        code='title = Text("竖屏")',
        audio=None,
    )

    script = _build_manim_script([scene], resolution=(1080, 1920))

    assert "config.pixel_width = 1080" in script
    assert "config.pixel_height = 1920" in script
    assert "config.frame_width = 4.500000" in script
    assert "config.frame_height = 8.0" in script


async def test_validate_code_stops_at_first_runtime_error():
    scene = SceneInput(
        scene_index=0,
        narration="",
        description="验证运行时错误立即停止",
        code='raise RuntimeError("root failure")\nraise ValueError("cascade noise")',
        audio=None,
    )

    is_valid, errors = await ManimRenderEngine().validate_code([scene])

    assert is_valid is False
    assert "RuntimeError: root failure" in errors
    assert "cascade noise" not in errors
    assert "DRY_RUN_COLLECTED_ERRORS" not in errors
