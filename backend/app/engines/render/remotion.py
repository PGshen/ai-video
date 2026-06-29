import logging
from pathlib import Path

from app.engines.render.base import RenderEngine, RenderRequest, RenderResult, SceneInput
from app.engines.render.manim import _RenderResultWithBytes

logger = logging.getLogger(__name__)

_REMOTION_IMPORTS = """\
import React from 'react';
import {
  AbsoluteFill, Sequence, Audio,
  useCurrentFrame, useVideoConfig,
  interpolate, spring,
} from 'remotion';"""


def _build_remotion_tsx(scenes: list[SceneInput], fps: int = 30) -> str:
    """Generate a complete VideoScene.tsx from a list of SceneInput."""
    durations: list[int] = []
    for scene in scenes:
        if scene.audio:
            frames = round(scene.audio.duration_seconds * fps)
        else:
            frames = round(5.0 * fps)  # fallback default
        durations.append(max(frames, 1))

    total = sum(durations)
    lines: list[str] = [
        _REMOTION_IMPORTS,
        "",
        f"export const totalFrames = {total};",
        "",
        "export const VideoScene: React.FC = () => {",
        "  const frame = useCurrentFrame();",
        "  const { fps } = useVideoConfig();",
        "  return (",
        "    <AbsoluteFill>",
    ]

    offset = 0
    for i, (scene, dur) in enumerate(zip(scenes, durations)):
        audio_line = ""
        if scene.audio and scene.audio.audio_path:
            audio_line = f'        <Audio src="file://{scene.audio.audio_path}" />'

        lines.append(f"      {{/* Scene {i}: {scene.description} */}}")
        lines.append(f"      <Sequence from={{{offset}}} durationInFrames={{{dur}}}>")
        if audio_line:
            lines.append(audio_line)
        lines.append("        {(() => {")
        for code_line in scene.code.splitlines():
            lines.append(f"          {code_line}")
        lines.append("        })()}")
        lines.append("      </Sequence>")
        offset += dur

    lines += [
        "    </AbsoluteFill>",
        "  );",
        "};",
        "",
    ]
    return "\n".join(lines)


class RemotionRenderEngine:
    engine_name = "remotion"

    async def validate_code(self, scenes: list[SceneInput]) -> tuple[bool, str]:
        return True, ""

    async def render(self, request: RenderRequest, work_dir: str | None = None) -> RenderResult:
        raise NotImplementedError("render() will be implemented in Task 3")

    async def health_check(self) -> bool:
        remotion_bin = Path("remotion-template/node_modules/.bin/remotion")
        return remotion_bin.exists()
