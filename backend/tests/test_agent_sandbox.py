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
