import asyncio
import contextlib
import os
import tempfile
from pathlib import Path
from app.engines.render.base import RenderEngine, RenderRequest, RenderResult, SceneInput
from app.config import settings


@contextlib.contextmanager
def _tmpdir_context(work_dir):
    if work_dir is not None:
        yield work_dir
    else:
        with tempfile.TemporaryDirectory() as d:
            yield d


class ManimRenderEngine:
    engine_name = "manim"

    async def validate_code(self, scenes: list[SceneInput]) -> tuple[bool, str]:
        return True, ""

    async def render(self, request: RenderRequest, work_dir: str | None = None) -> RenderResult:
        with _tmpdir_context(work_dir) as tmpdir:
            script_path = os.path.join(tmpdir, "scene.py")
            output_path = os.path.join(tmpdir, "output.mp4")
            script_content = _build_manim_script(request.scenes)

            with open(script_path, "w") as f:
                f.write(script_content)

            cmd = [
                "python", "-m", "manim", "render",
                script_path, "MainScene",
                "--output_file", output_path,
                "--format", "mp4",
                "--media_dir", tmpdir,
                "-q", "l",  # low quality (480p) for faster rendering
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=tmpdir,
            )
            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=settings.MANIM_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                proc.terminate()
                await proc.wait()
                return RenderResult(
                    success=False,
                    output_path=None,
                    duration_seconds=None,
                    error_message="Manim render timed out",
                    render_log="Render timed out after timeout limit",
                )

            render_log = stdout.decode(errors="replace") if stdout else ""

            if proc.returncode != 0:
                log_tail = render_log[-1500:].strip() if render_log else ""
                return RenderResult(
                    success=False,
                    output_path=None,
                    duration_seconds=None,
                    error_message=f"Manim exited with code {proc.returncode}\n{log_tail}",
                    render_log=render_log,
                )

            # Manim may place output in a subdirectory; find the mp4
            actual_output = _find_output_video(tmpdir, output_path)
            if actual_output is None:
                return RenderResult(
                    success=False,
                    output_path=None,
                    duration_seconds=None,
                    error_message="Output video file not found after render",
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
        proc = await asyncio.create_subprocess_exec(
            "python", "-m", "manim", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0


class _RenderResultWithBytes(RenderResult):
    def __init__(self, *args, video_bytes: bytes, **kwargs):
        super().__init__(*args, **kwargs)
        self.video_bytes = video_bytes


def _build_manim_script(scenes: list[SceneInput]) -> str:
    lines = [
        "from manim import *",
        "",
        "",
        "class MainScene(Scene):",
        "    def construct(self):",
    ]
    for i, scene in enumerate(scenes):
        audio_path = scene.audio.audio_path if scene.audio else f"scene_{i}_audio.mp3"
        lines.append(f"        # Scene {i}: {scene.description}")
        lines.append(f'        self.add_sound("{audio_path}")')
        for code_line in scene.code.splitlines():
            lines.append(f"        {code_line}")
        lines.append("")
    return "\n".join(lines)


def _find_output_video(tmpdir: str, expected_path: str) -> str | None:
    if os.path.exists(expected_path):
        return expected_path
    for root, _, files in os.walk(tmpdir):
        for fname in files:
            if fname.endswith(".mp4"):
                return os.path.join(root, fname)
    return None
