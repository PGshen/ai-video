import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.strategies.agent_sandbox import (
    build_validate_server,
    read_scene_codes,
    validate_workdir,
    write_sandbox,
)

SCENES = [
    {"scene_index": 0, "narration": "旁白零", "description": "描述零", "beats": []},
    {"scene_index": 1, "narration": "旁白一", "description": "描述一", "beats": []},
]


def test_write_sandbox_creates_input_style_and_scenes_dir(tmp_path):
    write_sandbox(
        str(tmp_path),
        scenes=SCENES,
        style_components={"color_scheme": "蓝色"},
        aspect_ratio="landscape",
        render_engine="manim",
    )
    payload = json.loads((tmp_path / "input.json").read_text())
    assert len(payload["scenes"]) == 2
    assert payload["scenes"][0]["narration"] == "旁白零"
    style = (tmp_path / "STYLE.md").read_text()
    assert "蓝色" in style
    assert "landscape" in style
    assert (tmp_path / "scenes").is_dir()


def test_style_md_carries_engine_constraints(tmp_path):
    """STYLE.md 必须带上引擎约束——缺了它 Agent 会写出通过校验却渲染黑屏的代码。

    回归背景：首次真实跑通时 13 个镜头全黑，原因是 Agent 未拿到「禁止写类定义、
    只写 construct() 方法体」这条契约，写出了从不被执行的 `class SceneNN(Scene)`。
    """
    write_sandbox(
        str(tmp_path),
        scenes=SCENES,
        style_components={"color_scheme": "蓝色"},
        aspect_ratio="landscape",
        render_engine="manim",
    )
    style = (tmp_path / "STYLE.md").read_text()
    assert "引擎约束" in style
    # 代码契约：来自 engine_specs/manim.yaml 的 code_prompt
    assert "禁止在 code 里写 def construct" in style
    # 画幅规则：来自 _build_aspect_ratio_prompt
    assert "安全区" in style


def test_read_scene_codes_returns_files_in_index_order(tmp_path):
    scenes_dir = tmp_path / "scenes"
    scenes_dir.mkdir()
    (scenes_dir / "scene_00.py").write_text("# zero")
    (scenes_dir / "scene_01.py").write_text("# one")
    assert read_scene_codes(str(tmp_path), 2) == ["# zero", "# one"]


def test_read_scene_codes_returns_empty_string_for_missing_file(tmp_path):
    (tmp_path / "scenes").mkdir()
    (tmp_path / "scenes" / "scene_00.py").write_text("# zero")
    assert read_scene_codes(str(tmp_path), 2) == ["# zero", ""]


@pytest.mark.asyncio
async def test_validate_workdir_reports_missing_scene_files(tmp_path):
    write_sandbox(
        str(tmp_path),
        scenes=SCENES,
        style_components={},
        aspect_ratio="landscape",
        render_engine="manim",
    )
    (tmp_path / "scenes" / "scene_00.py").write_text("# zero")
    is_valid, errors = await validate_workdir(str(tmp_path), SCENES, "manim")
    assert is_valid is False
    assert "scene_01.py" in errors


@pytest.mark.asyncio
async def test_validate_workdir_delegates_to_render_engine(tmp_path):
    write_sandbox(
        str(tmp_path),
        scenes=SCENES,
        style_components={},
        aspect_ratio="landscape",
        render_engine="manim",
    )
    (tmp_path / "scenes" / "scene_00.py").write_text("# zero")
    (tmp_path / "scenes" / "scene_01.py").write_text("# one")

    engine = MagicMock()
    engine.validate_code = AsyncMock(return_value=(False, "boom"))
    with patch(
        "app.services.strategies.agent_sandbox.get_render_engine", return_value=engine
    ):
        assert await validate_workdir(str(tmp_path), SCENES, "manim") == (False, "boom")
    passed = engine.validate_code.await_args.args[0]
    assert [s.scene_index for s in passed] == [0, 1]
    assert passed[0].code == "# zero"


def _capture_validate_handler(tmp_path):
    captured = {}

    def fake_create(*, name, version, tools):
        captured["tools"] = tools
        return {"type": "sdk", "name": name}

    with patch("claude_agent_sdk.create_sdk_mcp_server", fake_create):
        server, tool_name = build_validate_server(str(tmp_path), SCENES, "manim")
    assert tool_name == "mcp__codegen__validate"
    return captured["tools"][0].handler


@pytest.mark.asyncio
async def test_validate_tool_handler_returns_ok_text_on_success(tmp_path):
    handler = _capture_validate_handler(tmp_path)
    with patch(
        "app.services.strategies.agent_sandbox.validate_workdir",
        AsyncMock(return_value=(True, "")),
    ):
        result = await handler({})
    assert result["content"][0]["text"] == "校验通过。"
    assert "is_error" not in result


@pytest.mark.asyncio
async def test_validate_tool_handler_returns_error_with_details(tmp_path):
    handler = _capture_validate_handler(tmp_path)
    with patch(
        "app.services.strategies.agent_sandbox.validate_workdir",
        AsyncMock(return_value=(False, "scene 1: NameError")),
    ):
        result = await handler({})
    assert result["is_error"] is True
    assert "scene 1: NameError" in result["content"][0]["text"]


def test_style_md_only_carries_codegen_relevant_components(tmp_path):
    """narrative_style / exemplar 是叙事侧组件，不该进代码沙箱。

    它们在 Agent 会话里每轮都会被重新携带，是纯粹的成本浪费；提示词模式的
    代码提示词也只取 color_scheme + animation_style。
    """
    from app.services.strategies.agent_sandbox import write_sandbox

    write_sandbox(
        str(tmp_path),
        scenes=[{"scene_index": 0, "narration": "旁白", "description": "描述"}],
        style_components={
            "color_scheme": "COLOR_MARKER",
            "animation_style": "ANIM_MARKER",
            "narrative_style": "NARRATIVE_MARKER",
            "exemplar": "EXEMPLAR_MARKER",
        },
        aspect_ratio="landscape",
        render_engine="manim",
    )
    style = (tmp_path / "STYLE.md").read_text(encoding="utf-8")
    assert "COLOR_MARKER" in style
    assert "ANIM_MARKER" in style
    assert "NARRATIVE_MARKER" not in style, "叙事组件不该进代码沙箱"
    assert "EXEMPLAR_MARKER" not in style, "叙事金样本不该进代码沙箱"


def test_input_json_drops_tts_alignment_bookkeeping(tmp_path):
    """beats 里的对齐记账字段不进沙箱，但同步用的时间轴必须保留。"""
    import json

    from app.services.strategies.agent_sandbox import write_sandbox

    beat = {
        "beat_index": 0,
        "visual_action": "画一条时间轴",
        "cue_text": "假如人活到80岁",
        "emphasis": "80岁",
        "transition": "reveal",
        "animation_start_seconds": 0.095,
        "animation_end_seconds": 2.085,
        "speech_start_seconds": 0.275,
        "speech_end_seconds": 1.965,
        "cue_start_char": 0,
        "cue_end_char": 9,
        "fallback_weight": 1.0,
        "alignment_status": "aligned",
    }
    write_sandbox(
        str(tmp_path),
        scenes=[{"scene_index": 0, "narration": "旁白", "description": "描述", "beats": [beat]}],
        style_components={"color_scheme": "c", "animation_style": "a"},
        aspect_ratio="landscape",
        render_engine="manim",
    )
    written = json.loads((tmp_path / "input.json").read_text(encoding="utf-8"))
    kept = written["scenes"][0]["beats"][0]
    for field in ("visual_action", "animation_start_seconds", "speech_end_seconds", "transition"):
        assert field in kept, f"{field} 是代码生成需要的，不该被裁掉"
    for field in ("cue_start_char", "cue_end_char", "fallback_weight", "alignment_status"):
        assert field not in kept, f"{field} 是 TTS 对齐记账，不该进沙箱"
