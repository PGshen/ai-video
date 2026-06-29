import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path

from app.config import settings
from app.engines.render.base import RenderRequest, RenderResult, SceneInput
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


def _find_output_video(tmpdir: str, expected_path: str) -> str | None:
    if os.path.exists(expected_path):
        return expected_path
    for root, _, files in os.walk(tmpdir):
        for fname in files:
            if fname.endswith(".mp4"):
                return os.path.join(root, fname)
    return None


class RemotionRenderEngine:
    engine_name = "remotion"

    async def validate_code(self, scenes: list[SceneInput]) -> tuple[bool, str]:
        return True, ""

    async def render(self, request: RenderRequest, work_dir: str | None = None) -> RenderResult:
        import contextlib

        @contextlib.contextmanager
        def _tmpdir_ctx(d):
            if d is not None:
                yield d
            else:
                with tempfile.TemporaryDirectory() as td:
                    yield td

        with _tmpdir_ctx(work_dir) as tmpdir:
            return await self._render_in_dir(request, tmpdir)

    async def _render_in_dir(self, request: RenderRequest, tmpdir: str) -> RenderResult:
        template_dir = Path(settings.REMOTION_TEMPLATE_DIR).resolve()
        node_modules_src = template_dir / "node_modules"

        # Copy template files into tmpdir
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir(exist_ok=True)
        for fname in ["package.json", "tsconfig.json", "remotion.config.ts"]:
            shutil.copy2(template_dir / fname, Path(tmpdir) / fname)
        shutil.copy2(template_dir / "src" / "index.tsx", src_dir / "index.tsx")
        shutil.copy2(template_dir / "src" / "Root.tsx", src_dir / "Root.tsx")

        # Symlink node_modules
        node_modules_link = Path(tmpdir) / "node_modules"
        if not node_modules_link.exists():
            os.symlink(str(node_modules_src), str(node_modules_link))

        # Write generated VideoScene.tsx
        tsx_content = _build_remotion_tsx(request.scenes, fps=request.fps)
        (src_dir / "VideoScene.tsx").write_text(tsx_content, encoding="utf-8")

        output_path = str(Path(tmpdir) / "output.mp4")
        remotion_bin = str(node_modules_src / ".bin" / "remotion")
        cmd = [remotion_bin, "render", "VideoScene", output_path, "--fps", str(request.fps)]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=tmpdir,
        )

        log_lines: list[str] = []
        try:
            async with asyncio.timeout(settings.REMOTION_TIMEOUT_SECONDS):
                async for raw in proc.stdout:
                    line = raw.decode(errors="replace").rstrip()
                    log_lines.append(line)
                    logger.info("[Remotion] %s", line)
                await proc.wait()
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return RenderResult(
                success=False,
                output_path=None,
                duration_seconds=None,
                error_message=f"Remotion render timed out after {settings.REMOTION_TIMEOUT_SECONDS:.0f}s",
                render_log="\n".join(log_lines),
            )

        render_log = "\n".join(log_lines)

        if proc.returncode != 0:
            return RenderResult(
                success=False,
                output_path=None,
                duration_seconds=None,
                error_message=f"Remotion exited with code {proc.returncode}\n{render_log.strip()}",
                render_log=render_log,
            )

        actual_output = _find_output_video(tmpdir, output_path)
        if actual_output is None:
            return RenderResult(
                success=False,
                output_path=None,
                duration_seconds=None,
                error_message="Output video file not found after Remotion render",
                render_log=render_log,
            )

        video_bytes = Path(actual_output).read_bytes()
        return _RenderResultWithBytes(
            success=True,
            output_path=actual_output,
            duration_seconds=None,
            error_message=None,
            render_log=render_log,
            video_bytes=video_bytes,
        )

    async def health_check(self) -> bool:
        remotion_bin = Path(settings.REMOTION_TEMPLATE_DIR).resolve() / "node_modules" / ".bin" / "remotion"
        return remotion_bin.exists()
