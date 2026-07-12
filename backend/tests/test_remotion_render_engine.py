from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.render.base import RenderRequest, SceneAudio, SceneInput
from app.engines.render.remotion import _build_remotion_tsx, _scene_index_by_line, _tsc_check


def _make_scene(index: int, code: str, duration: float = 5.0, audio_path: str | None = None) -> SceneInput:
    return SceneInput(
        scene_index=index,
        narration=f"narration {index}",
        description=f"desc {index}",
        code=code,
        audio=SceneAudio(
            scene_index=index,
            audio_path=audio_path or f"/tmp/scene_{index}.mp3",
            duration_seconds=duration,
        ) if audio_path is not None else None,
    )


def test_build_remotion_tsx_exports_total_frames():
    scenes = [
        _make_scene(0, "return <div/>", duration=5.0, audio_path="/tmp/s0.mp3"),
        _make_scene(1, "return <div/>", duration=3.0, audio_path="/tmp/s1.mp3"),
    ]
    tsx = _build_remotion_tsx(scenes, fps=30)
    # 5.0s * 30fps = 150, 3.0s * 30fps = 90, total = 240
    assert "export const totalFrames = 240;" in tsx


def test_build_remotion_tsx_sequence_boundaries():
    scenes = [
        _make_scene(0, "return <div/>", duration=4.0, audio_path="/tmp/s0.mp3"),
        _make_scene(1, "return <div/>", duration=6.0, audio_path="/tmp/s1.mp3"),
    ]
    tsx = _build_remotion_tsx(scenes, fps=30)
    # scene 0: from=0, duration=120
    assert "from={0}" in tsx
    assert "durationInFrames={120}" in tsx
    # scene 1: from=120, duration=180
    assert "from={120}" in tsx
    assert "durationInFrames={180}" in tsx


def test_build_remotion_tsx_audio_src():
    scenes = [
        _make_scene(0, "return <div/>", duration=3.0, audio_path="/tmp/my_audio.mp3"),
    ]
    tsx = _build_remotion_tsx(scenes, fps=30)
    assert "staticFile('my_audio.mp3')" in tsx


def test_build_remotion_tsx_no_audio_uses_estimated_duration():
    scene = SceneInput(
        scene_index=0,
        narration="narration",
        description="desc",
        code="return <div/>",
        audio=None,
    )
    tsx = _build_remotion_tsx([scene], fps=30)
    # fallback 5.0s * 30fps = 150
    assert "durationInFrames={150}" in tsx


def test_build_remotion_tsx_wraps_code_in_named_component():
    scenes = [
        _make_scene(0, "const x = 1;\nreturn <div>{x}</div>", duration=2.0, audio_path="/tmp/s0.mp3"),
    ]
    tsx = _build_remotion_tsx(scenes, fps=30)
    assert "const _Scene0 = () => {" in tsx
    assert "const x = 1;" in tsx
    assert "<_Scene0 />" in tsx


def test_build_remotion_tsx_injects_scene_duration():
    scenes = [
        _make_scene(0, "return <div/>", duration=4.0, audio_path="/tmp/s0.mp3"),
    ]
    tsx = _build_remotion_tsx(scenes, fps=30)
    # 4.0s * 30fps = 120 frames, injected as _sceneDuration to avoid name collision
    assert "const _sceneDuration = 120;" in tsx


def test_build_remotion_tsx_strips_llm_self_declared_scene_duration():
    scenes = [
        _make_scene(0, "const _sceneDuration = 176;\nreturn <div/>", duration=4.0, audio_path="/tmp/s0.mp3"),
        _make_scene(1, "const _sceneDuration = 241;\nreturn <div/>", duration=3.0, audio_path="/tmp/s1.mp3"),
    ]
    tsx = _build_remotion_tsx(scenes, fps=30)
    # Only the engine-injected declarations should remain, one per scene.
    assert tsx.count("const _sceneDuration = 176;") == 0
    assert tsx.count("const _sceneDuration = 241;") == 0
    assert tsx.count("const _sceneDuration =") == 2


def test_build_remotion_tsx_imports_remotion_apis():
    tsx = _build_remotion_tsx([_make_scene(0, "return <div/>", duration=2.0, audio_path="/tmp/s0.mp3")])
    assert "from 'remotion'" in tsx
    assert "useCurrentFrame" in tsx
    assert "AbsoluteFill" in tsx
    assert "Sequence" in tsx
    assert "Audio" in tsx


def _async_line_iter(lines: list[bytes]):
    async def _gen():
        for line in lines:
            yield line
    return _gen()


@pytest.mark.asyncio
async def test_remotion_render_engine_success():
    from app.engines.render.remotion import RemotionRenderEngine

    engine = RemotionRenderEngine()
    scene = SceneInput(
        scene_index=0,
        narration="hello",
        description="intro",
        code="return <div>Hello</div>;",
        audio=SceneAudio(
            scene_index=0,
            audio_path="/tmp/s0.mp3",
            duration_seconds=3.0,
        ),
    )
    request = RenderRequest(
        scenes=[scene],
        output_format="mp4",
        resolution=(1280, 720),
        fps=30,
    )

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = _async_line_iter([b"Rendering...\n", b"Done.\n"])

    async def fake_wait():
        return 0

    fake_proc.wait = fake_wait

    fake_video_bytes = b"fake-mp4-content"

    with patch("asyncio.create_subprocess_exec", return_value=fake_proc), \
         patch("app.engines.render.remotion._find_output_video", return_value="/tmp/output.mp4"), \
         patch("pathlib.Path.read_bytes", return_value=fake_video_bytes), \
         patch("shutil.copy2") as copy_mock, \
         patch("os.symlink"), \
         patch("pathlib.Path.mkdir"), \
         patch("pathlib.Path.write_text"):
        result = await engine.render(request)

    assert result.success is True
    assert result.video_bytes == fake_video_bytes
    assert "Rendering..." in result.render_log
    copied_sources = [str(call.args[0]) for call in copy_mock.call_args_list]
    assert any(source.endswith("/src/index.css") for source in copied_sources)


def test_scene_index_by_line_attributes_lines_to_owning_scene():
    scenes = [
        _make_scene(0, "const a = 1;\nreturn <div/>", duration=2.0, audio_path="/tmp/s0.mp3"),
        _make_scene(1, "const b = 2;\nreturn <div/>", duration=2.0, audio_path="/tmp/s1.mp3"),
    ]
    tsx = _build_remotion_tsx(scenes, fps=30)
    lines = tsx.splitlines()
    mapping = _scene_index_by_line(tsx)

    scene0_body_line = next(i for i, l in enumerate(lines, start=1) if "const a = 1;" in l)
    scene1_body_line = next(i for i, l in enumerate(lines, start=1) if "const b = 2;" in l)
    assert mapping[scene0_body_line] == 0
    assert mapping[scene1_body_line] == 1

    # Lines outside any _SceneN block (imports, exports, JSX composition) are unmapped.
    import_line = next(i for i, l in enumerate(lines, start=1) if l.startswith("import React"))
    assert import_line not in mapping


@pytest.mark.asyncio
async def test_tsc_check_attributes_error_to_owning_scene():
    scenes = [
        _make_scene(0, "return <div/>", duration=2.0, audio_path="/tmp/s0.mp3"),
        _make_scene(1, "const opacity = retreat;\nreturn <div/>", duration=2.0, audio_path="/tmp/s1.mp3"),
    ]
    tsx = _build_remotion_tsx(scenes, fps=30)
    lines = tsx.splitlines()
    error_line = next(i for i, l in enumerate(lines, start=1) if "const opacity = retreat;" in l)

    fake_proc = MagicMock()
    fake_proc.returncode = 2
    fake_proc.communicate = AsyncMock(
        return_value=(
            f"src/VideoScene.tsx({error_line},19): error TS2304: Cannot find name 'retreat'.\n".encode(),
            b"",
        )
    )

    with patch("asyncio.create_subprocess_exec", return_value=fake_proc), \
         patch("shutil.copy2"), patch("os.symlink"):
        errors = await _tsc_check(tsx, Path("/fake/template"))

    assert len(errors) == 1
    assert "scene 1:" in errors[0]
    assert "TS2304" in errors[0]
    assert "retreat" in errors[0]


@pytest.mark.asyncio
async def test_tsc_check_returns_no_errors_on_success():
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.communicate = AsyncMock(return_value=(b"", b""))

    with patch("asyncio.create_subprocess_exec", return_value=fake_proc), \
         patch("shutil.copy2"), patch("os.symlink"):
        errors = await _tsc_check("export const x = 1;", Path("/fake/template"))

    assert errors == []


@pytest.mark.asyncio
async def test_remotion_validate_code_reports_tsc_failures():
    from app.engines.render.remotion import RemotionRenderEngine

    scene = SceneInput(
        scene_index=0,
        narration="hello",
        description="intro",
        code="const opacity = retreat;\nreturn <div/>;",
        audio=None,
    )

    with patch("app.engines.render.remotion._tsc_check", new=AsyncMock(return_value=["scene 0: TS2304: Cannot find name 'retreat'."])):
        is_valid, errors = await RemotionRenderEngine().validate_code([scene])

    assert is_valid is False
    assert "retreat" in errors


@pytest.mark.asyncio
async def test_remotion_validate_code_passes_when_tsc_clean():
    from app.engines.render.remotion import RemotionRenderEngine

    scene = SceneInput(scene_index=0, narration="hello", description="intro", code="return <div/>;", audio=None)

    with patch("app.engines.render.remotion._tsc_check", new=AsyncMock(return_value=[])):
        is_valid, errors = await RemotionRenderEngine().validate_code([scene])

    assert is_valid is True
    assert errors == ""


@pytest.mark.asyncio
async def test_remotion_render_engine_nonzero_exit():
    from app.engines.render.remotion import RemotionRenderEngine

    engine = RemotionRenderEngine()
    scene = SceneInput(
        scene_index=0,
        narration="hello",
        description="intro",
        code="return <div/>;",
        audio=None,
    )
    request = RenderRequest(scenes=[scene], output_format="mp4", resolution=(1280, 720), fps=30)

    fake_proc = MagicMock()
    fake_proc.returncode = 1
    fake_proc.stdout = _async_line_iter([b"Error: syntax\n"])

    async def fake_wait():
        return 1

    fake_proc.wait = fake_wait

    with patch("asyncio.create_subprocess_exec", return_value=fake_proc), \
         patch("shutil.copy2"), \
         patch("os.symlink"), \
         patch("pathlib.Path.mkdir"), \
         patch("pathlib.Path.write_text"):
        result = await engine.render(request)

    assert result.success is False
    assert "exited with code 1" in result.error_message
