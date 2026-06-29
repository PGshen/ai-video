from app.engines.render.base import SceneInput, SceneAudio
from app.engines.render.remotion import _build_remotion_tsx


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
    assert 'src="file:///tmp/my_audio.mp3"' in tsx


def test_build_remotion_tsx_no_audio_uses_estimated_duration():
    scene = SceneInput(
        scene_index=0,
        narration="narration",
        description="desc",
        code="return <div/>",
        audio=None,
    )
    # When no audio, scenes dict may carry estimated_duration_seconds separately.
    # _build_remotion_tsx receives SceneInput; without audio it falls back to 5.0s default.
    tsx = _build_remotion_tsx([scene], fps=30)
    # fallback 5.0s * 30fps = 150
    assert "durationInFrames={150}" in tsx


def test_build_remotion_tsx_wraps_code_in_iife():
    scenes = [
        _make_scene(0, "const x = 1;\nreturn <div>{x}</div>", duration=2.0, audio_path="/tmp/s0.mp3"),
    ]
    tsx = _build_remotion_tsx(scenes, fps=30)
    assert "(() => {" in tsx
    assert "const x = 1;" in tsx


def test_build_remotion_tsx_imports_remotion_apis():
    tsx = _build_remotion_tsx([_make_scene(0, "return <div/>", duration=2.0, audio_path="/tmp/s0.mp3")])
    assert "from 'remotion'" in tsx
    assert "useCurrentFrame" in tsx
    assert "AbsoluteFill" in tsx
    assert "Sequence" in tsx
    assert "Audio" in tsx
