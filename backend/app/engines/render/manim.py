import asyncio
import ast
import contextlib
import logging
import os
import re
import tempfile
from pathlib import Path

import pyflakes.checker
import pyflakes.messages as pyflakes_messages

from app.config import settings
from app.engines.render.base import RenderEngine, RenderRequest, RenderResult, RenderResultWithBytes, SceneInput

logger = logging.getLogger(__name__)


_CHINESE_TEX_TEMPLATE_LINES = [
    '_chinese_tex_template = TexTemplate(tex_compiler="xelatex", output_format=".xdv")',
    r'_chinese_tex_template.add_to_preamble(r"\usepackage[UTF8,fontset=fandol]{ctex}")',
]
_DOUBLE_ESCAPED_TEX_COMMAND = re.compile(r"\\\\(?=[A-Za-z])")
_PROGRESS_BAR_RE = re.compile(r"\d+%\|")
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_TEX_CONSTRUCTORS = {
    "BulletedList",
    "MathTex",
    "SingleStringMathTex",
    "Tex",
    "Title",
}


class _TexStringNormalizer(ast.NodeTransformer):
    """Repair LaTeX commands that were double-escaped by JSON/code generation."""

    def __init__(self) -> None:
        self.changed = False

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if not isinstance(node.value, str):
            return node

        normalized = _DOUBLE_ESCAPED_TEX_COMMAND.sub(r"\\", node.value)
        if normalized == node.value:
            return node

        self.changed = True
        return ast.copy_location(ast.Constant(value=normalized), node)


class _ManimImportStripper(ast.NodeTransformer):
    """Drop AI-generated ``import manim`` statements from per-scene code.

    ``_build_manim_script`` already emits ``from manim import *`` once at
    module level. When the model repeats it inside ``construct()``, it's a
    non-module-level import statement that pyflakes/Python reject.
    """

    def __init__(self) -> None:
        self.changed = False

    def visit_Import(self, node: ast.Import) -> ast.AST | None:
        if any(alias.name.partition(".")[0] == "manim" for alias in node.names):
            self.changed = True
            return None
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST | None:
        if node.module and node.module.partition(".")[0] == "manim":
            self.changed = True
            return None
        return node


class _TexTemplateInjector(ast.NodeTransformer):
    """Make generated Tex/MathTex calls use a Chinese-capable template."""

    def __init__(self) -> None:
        self.source_changed = False
        self.template_injected = False

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if not _is_tex_constructor(node.func):
            return node

        normalizer = _TexStringNormalizer()
        node.args = [normalizer.visit(argument) for argument in node.args]
        if normalizer.changed:
            self.source_changed = True

        if any(keyword.arg == "tex_template" for keyword in node.keywords):
            return node

        node.keywords.append(
            ast.keyword(
                arg="tex_template",
                value=ast.Name(id="_chinese_tex_template", ctx=ast.Load()),
            )
        )
        self.source_changed = True
        self.template_injected = True
        return node


# Pyflakes message types that are noise when `from manim import *` is present:
# - ImportStarUsed: always fires for the wildcard import itself
# - UndefinedName / UndefinedLocal: pyflakes can't see inside the star, so it
#   falsely flags every Manim name (Circle, Text, Scene, …) as undefined
# - UnusedVariable: an assigned-but-unused local doesn't affect runtime
#   behavior, so it's not worth triggering a repair round over
# - UnusedImport: an unused import doesn't affect runtime behavior either
_PYFLAKES_STAR_NOISE = (
    pyflakes_messages.ImportStarUsed,
    pyflakes_messages.ImportStarUsage,  # "'X' may be undefined, or defined from star imports"
    pyflakes_messages.UndefinedName,
    pyflakes_messages.UndefinedLocal,
    pyflakes_messages.UnusedVariable,
    pyflakes_messages.UnusedImport,
)


def _static_check(script: str) -> list[str]:
    """Return actionable pyflakes diagnostics for the assembled Manim script.

    Star-import noise is filtered out because ``from manim import *`` makes it
    impossible for pyflakes to resolve Manim names statically.
    """
    try:
        tree = ast.parse(script)
    except SyntaxError as exc:
        return [f"SyntaxError: {exc}"]
    w = pyflakes.checker.Checker(tree, "<manim_generated>")
    return [
        str(msg) for msg in w.messages
        if not isinstance(msg, _PYFLAKES_STAR_NOISE)
    ]


def _is_tex_constructor(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id in _TEX_CONSTRUCTORS
    if isinstance(node, ast.Attribute):
        return node.attr in _TEX_CONSTRUCTORS
    return False


def _prepare_manim_code(code: str) -> tuple[str, bool]:
    """Prepare generated formulas for reliable Chinese LaTeX rendering.

    Tex/MathTex calls receive a Chinese-capable template, and doubled command
    escapes such as ``\\frac`` are repaired without changing LaTeX ``\\ ``
    line breaks.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Keep the original source so Manim can report the actual code error.
        return code, False

    stripper = _ManimImportStripper()
    tree = stripper.visit(tree)

    injector = _TexTemplateInjector()
    tree = injector.visit(tree)

    if not stripper.changed and not injector.source_changed:
        return code, False

    ast.fix_missing_locations(tree)
    return ast.unparse(tree), injector.template_injected


# Runs the scene directly instead of going through `manim render`, because the
# CLI catches exceptions with a rich pretty-printed panel (`error_console.
# print_exception()`) that wraps to a fixed width and buries the actual
# exception type/message dozens of lines into a boxed traceback — useless
# once truncated for logging. A plain `traceback.print_exc()` keeps the
# exception type and message on the last line, always.
_DRY_RUN_DRIVER = """
import sys
import traceback

from manim import config

config.dry_run = True
config.disable_caching = True

sys.path.insert(0, {tmpdir!r})
try:
    from scene import MainScene
    MainScene().render()
except Exception:
    traceback.print_exc()
    sys.exit(1)
sys.exit(0)
"""


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
        script = _build_manim_script(scenes, include_audio=False)

        static_errors = _static_check(script)
        if static_errors:
            logger.info("[ManimValidate] static errors: %d\n%s", len(static_errors), "\n".join(static_errors))
            return False, "\n".join(static_errors)

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "scene.py")
            with open(script_path, "w") as f:
                f.write(script)

            driver_path = os.path.join(tmpdir, "_dry_run_driver.py")
            with open(driver_path, "w") as f:
                f.write(_DRY_RUN_DRIVER.format(tmpdir=tmpdir))

            cmd = ["python", driver_path]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=tmpdir,
            )
            try:
                async with asyncio.timeout(120):
                    output, _ = await proc.communicate()
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return False, "Dry-run timed out after 120s"

            log = output.decode(errors="replace")
            if proc.returncode != 0:
                # The exception type/message is on the last lines of a
                # traceback, so tail the log rather than truncating its head.
                filtered_log = "\n".join(
                    line
                    for line in (
                        _ANSI_ESCAPE_RE.sub("", raw_line).strip()
                        for raw_line in re.split(r"[\r\n]", log)
                    )
                    if line
                    and "Caching disabled" not in line
                    and not _PROGRESS_BAR_RE.search(line)
                )
                logger.info("[ManimValidate] dry_run failed:\n%s", filtered_log[-2000:])
                return False, filtered_log[-2000:]

            logger.info("[ManimValidate] dry_run passed")
            return True, ""

    async def render(self, request: RenderRequest, work_dir: str | None = None) -> RenderResult:
        with _tmpdir_context(work_dir) as tmpdir:
            script_path = os.path.join(tmpdir, "scene.py")
            output_path = os.path.join(tmpdir, "output.mp4")
            script_content = _build_manim_script(
                request.scenes,
                resolution=request.resolution,
            )

            with open(script_path, "w") as f:
                f.write(script_content)

            cmd = [
                "python", "-m", "manim", "render",
                script_path, "MainScene",
                "--output_file", output_path,
                "--format", "mp4",
                "--media_dir", tmpdir,
                "--resolution", f"{request.resolution[0]},{request.resolution[1]}",
                "--fps", str(request.fps),
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=tmpdir,
            )

            log_lines: list[str] = []
            try:
                async with asyncio.timeout(settings.MANIM_TIMEOUT_SECONDS):
                    async for raw in proc.stdout:
                        line = raw.decode(errors="replace").rstrip()
                        log_lines.append(line)
                        logger.info("[Manim] %s", line)
                    await proc.wait()
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                render_log = "\n".join(log_lines)
                return RenderResult(
                    success=False,
                    output_path=None,
                    duration_seconds=None,
                    error_message=f"Manim render timed out after {settings.MANIM_TIMEOUT_SECONDS:.0f}s",
                    render_log=render_log,
                )

            render_log = "\n".join(log_lines)

            if proc.returncode != 0:
                return RenderResult(
                    success=False,
                    output_path=None,
                    duration_seconds=None,
                    error_message=f"Manim exited with code {proc.returncode}\n{render_log.strip() if render_log else ''}",
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
            return RenderResultWithBytes(
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



def _build_manim_script(
    scenes: list[SceneInput],
    include_audio: bool = True,
    resolution: tuple[int, int] | None = None,
) -> str:
    prepared_scenes = []
    needs_chinese_tex_template = False
    for scene in scenes:
        prepared_code, changed = _prepare_manim_code(scene.code)
        prepared_scenes.append((scene, prepared_code))
        needs_chinese_tex_template = needs_chinese_tex_template or changed

    lines = [
        "from manim import *",
        "",
    ]
    if resolution is not None:
        width, height = resolution
        frame_width = 8.0 * width / height
        lines.extend([
            f"config.pixel_width = {width}",
            f"config.pixel_height = {height}",
            f"config.frame_width = {frame_width:.6f}",
            "config.frame_height = 8.0",
            "",
        ])
    if needs_chinese_tex_template:
        lines.extend(_CHINESE_TEX_TEMPLATE_LINES)
        lines.append("")
    lines.extend([
        "",
        "class MainScene(Scene):",
        "    def construct(self):",
    ])
    for i, (scene, prepared_code) in enumerate(prepared_scenes):
        lines.append(f"        # Scene {i}: {scene.description}")
        if include_audio:
            audio_path = scene.audio.audio_path if scene.audio else f"scene_{i}_audio.mp3"
            duration = scene.audio.duration_seconds if scene.audio else 0.0
            lines.append(f"        _t0_{i} = self.renderer.time")
            lines.append(f'        self.add_sound("{audio_path}")')
        for code_line in prepared_code.splitlines():
            lines.append(f"        {code_line}")
        if include_audio:
            lines.append(f"        _rem_{i} = {duration:.3f} - (self.renderer.time - _t0_{i})")
            lines.append(f"        if _rem_{i} > 0:")
            lines.append(f"            self.wait(_rem_{i})")
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
