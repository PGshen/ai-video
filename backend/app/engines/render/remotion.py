import asyncio
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

from app.config import settings
from app.engines.render.base import RenderRequest, RenderResult, RenderResultWithBytes, SceneInput

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _resolve_template_dir() -> Path:
    p = Path(settings.REMOTION_TEMPLATE_DIR)
    if p.is_absolute():
        return p
    return _REPO_ROOT / p


_SCENE_DURATION_DECL_RE = re.compile(r"^\s*const\s+_sceneDuration\s*=.*;\s*$")

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_NOISE_LINE_RE = re.compile(
    r"^(Rendered\s+\d+/\d+,\s*time remaining:.*|Bundling\s+\d+%.*|\d+%.*)$"
)

_REMOTION_IMPORTS = """\
import React from 'react';
import {
  AbsoluteFill, Sequence, Audio, staticFile,
  useCurrentFrame, useVideoConfig,
  interpolate, interpolateColors, spring,
} from 'remotion';"""

_SCENE_START_RE = re.compile(r"^const _Scene(\d+) = \(\) => \{$")
_SCENE_END_RE = re.compile(r"^\};$")
_TSC_ERROR_RE = re.compile(
    r"VideoScene\.tsx\((?P<line>\d+),(?P<col>\d+)\): error (?P<code>TS\d+): (?P<message>.+)"
)


def _build_remotion_tsx(scenes: list[SceneInput], fps: int = 30, resolution: tuple[int, int] = (1280, 720)) -> str:
    """Generate a complete VideoScene.tsx from a list of SceneInput."""
    request_width, request_height = resolution
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
        f"export const fps = {fps};",
        f"export const width = {request_width};",
        f"export const height = {request_height};",
        "",
    ]

    # Named sub-components must be defined BEFORE VideoScene (outside JSX)
    for i, (scene, dur) in enumerate(zip(scenes, durations)):
        lines.append(f"const _Scene{i} = () => {{")
        lines.append(f"  const _sceneDuration = {dur};  // total frames for this scene")
        for code_line in scene.code.splitlines():
            # The renderer is the sole authority on _sceneDuration; strip any
            # self-declaration the LLM may have emitted despite instructions,
            # to avoid a duplicate `const _sceneDuration` in the same scope.
            if _SCENE_DURATION_DECL_RE.match(code_line):
                continue
            lines.append(f"  {code_line}")
        lines.append("};")
        lines.append("")

    lines += [
        "export const VideoScene = () => (",
        "  <AbsoluteFill>",
    ]

    offset = 0
    for i, (scene, dur) in enumerate(zip(scenes, durations)):
        audio_line = ""
        if scene.audio and scene.audio.audio_path:
            filename = os.path.basename(scene.audio.audio_path)
            audio_line = f"      <Audio src={{staticFile('{filename}')}} />"

        lines.append(f"    {{/* Scene {i}: {scene.description} */}}")
        lines.append(f"    <Sequence from={{{offset}}} durationInFrames={{{dur}}}>")
        if audio_line:
            lines.append(audio_line)
        lines.append(f"      <_Scene{i} />")
        lines.append("    </Sequence>")
        offset += dur

    lines += [
        "  </AbsoluteFill>",
        ");",
        "",
    ]
    return "\n".join(lines)


def _scene_index_by_line(tsx: str) -> dict[int, int]:
    """Map each 1-indexed line number of the assembled tsx to its owning scene.

    Every scene's code lives inside its own ``const _SceneN = () => { ... };``
    block (see ``_build_remotion_tsx``), so a tsc diagnostic's line number can
    be attributed back to a single scene index for the repair prompt.
    """
    mapping: dict[int, int] = {}
    current: int | None = None
    for lineno, line in enumerate(tsx.splitlines(), start=1):
        start_match = _SCENE_START_RE.match(line)
        if start_match:
            current = int(start_match.group(1))
        if current is not None:
            mapping[lineno] = current
            if _SCENE_END_RE.match(line):
                current = None
    return mapping


async def _tsc_check(tsx: str, template_dir: Path) -> list[str]:
    """Type-check the assembled VideoScene.tsx with the real TypeScript compiler.

    Remotion's bundler (esbuild) only strips types during render and never
    reports errors like an undefined variable — those surface as an opaque
    browser-side ``ReferenceError`` mid-render instead, after minutes of
    rendering have already been spent. Running ``tsc --noEmit`` against the
    assembled file up front catches undefined names, syntax errors and type
    errors before a render is ever attempted.
    """
    line_to_scene = _scene_index_by_line(tsx)

    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()
        shutil.copy2(template_dir / "tsconfig.json", Path(tmpdir) / "tsconfig.json")
        shutil.copy2(template_dir / "src" / "index.tsx", src_dir / "index.tsx")
        shutil.copy2(template_dir / "src" / "Root.tsx", src_dir / "Root.tsx")
        shutil.copy2(template_dir / "src" / "index.css", src_dir / "index.css")
        (src_dir / "VideoScene.tsx").write_text(tsx, encoding="utf-8")

        node_modules_link = Path(tmpdir) / "node_modules"
        os.symlink(str(template_dir / "node_modules"), str(node_modules_link))

        tsc_bin = str(template_dir / "node_modules" / ".bin" / "tsc")
        proc = await asyncio.create_subprocess_exec(
            tsc_bin, "--noEmit", "--pretty", "false",
            cwd=tmpdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode(errors="replace")

    if proc.returncode == 0:
        return []

    errors: list[str] = []
    for match in _TSC_ERROR_RE.finditer(output):
        line = int(match.group("line"))
        scene_idx = line_to_scene.get(line)
        prefix = f"scene {scene_idx}: " if scene_idx is not None else ""
        errors.append(f"{prefix}{match.group('code')}: {match.group('message')}")

    if not errors:
        # tsc failed but nothing matched the diagnostic pattern (e.g. a
        # config/toolchain problem) — surface the raw output rather than
        # silently reporting an empty error list for a nonzero exit.
        errors.append(output.strip() or f"tsc exited with code {proc.returncode}")

    return errors


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
        template_dir = _resolve_template_dir()
        tsx = _build_remotion_tsx(scenes)
        errors = await _tsc_check(tsx, template_dir)
        if errors:
            logger.info("[RemotionValidate] tsc errors: %d\n%s", len(errors), "\n".join(errors))
            return False, "\n".join(errors)
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
        template_dir = _resolve_template_dir()
        node_modules_src = template_dir / "node_modules"

        # Copy template files into tmpdir
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir(exist_ok=True)
        for fname in ["package.json", "tsconfig.json", "remotion.config.ts"]:
            shutil.copy2(template_dir / fname, Path(tmpdir) / fname)
        shutil.copy2(template_dir / "src" / "index.tsx", src_dir / "index.tsx")
        shutil.copy2(template_dir / "src" / "Root.tsx", src_dir / "Root.tsx")
        shutil.copy2(template_dir / "src" / "index.css", src_dir / "index.css")

        # Symlink node_modules
        node_modules_link = Path(tmpdir) / "node_modules"
        if not node_modules_link.exists() and not node_modules_link.is_symlink():
            os.symlink(str(node_modules_src), str(node_modules_link))

        # Write generated VideoScene.tsx
        tsx_content = _build_remotion_tsx(request.scenes, fps=request.fps, resolution=request.resolution)
        (src_dir / "VideoScene.tsx").write_text(tsx_content, encoding="utf-8")

        output_path = str(Path(tmpdir) / "output.mp4")
        remotion_bin = str(node_modules_src / ".bin" / "remotion")
        cmd = [
            remotion_bin, "render", "VideoScene", output_path,
            "--fps", str(request.fps),
            "--width", str(request.resolution[0]),
            "--height", str(request.resolution[1]),
            "--public-dir", tmpdir,
        ]

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
                    decoded = raw.decode(errors="replace").rstrip("\n")
                    # Progress updates (bundling %, "Rendered x/y") are
                    # rewritten in place via \r; only the final frame in a
                    # chunk carries useful content, and even that is noise.
                    for fragment in decoded.split("\r"):
                        line = _ANSI_ESCAPE_RE.sub("", fragment).strip()
                        if not line or _NOISE_LINE_RE.match(line):
                            continue
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
        return RenderResultWithBytes(
            success=True,
            output_path=actual_output,
            duration_seconds=None,
            error_message=None,
            render_log=render_log,
            video_bytes=video_bytes,
        )

    async def health_check(self) -> bool:
        template_dir = _resolve_template_dir()
        remotion_bin = template_dir / "node_modules" / ".bin" / "remotion"
        return remotion_bin.exists()
