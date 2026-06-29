import asyncio
import ast
import contextlib
import logging
import os
import re
import tempfile
from pathlib import Path

from app.config import settings
from app.engines.render.base import RenderEngine, RenderRequest, RenderResult, SceneInput

logger = logging.getLogger(__name__)


_CHINESE_TEX_TEMPLATE_LINES = [
    '_chinese_tex_template = TexTemplate(tex_compiler="xelatex", output_format=".xdv")',
    r'_chinese_tex_template.add_to_preamble(r"\usepackage[UTF8,fontset=fandol]{ctex}")',
]
_DOUBLE_ESCAPED_TEX_COMMAND = re.compile(r"\\\\(?=[A-Za-z])")
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

    injector = _TexTemplateInjector()
    tree = injector.visit(tree)
    if not injector.source_changed:
        return code, False

    ast.fix_missing_locations(tree)
    return ast.unparse(tree), injector.template_injected


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
    if needs_chinese_tex_template:
        lines.extend(_CHINESE_TEX_TEMPLATE_LINES)
        lines.append("")
    lines.extend([
        "",
        "class MainScene(Scene):",
        "    def construct(self):",
        # "        self.camera.background_color = '#F5F0E8'",
    ])
    for i, (scene, prepared_code) in enumerate(prepared_scenes):
        audio_path = scene.audio.audio_path if scene.audio else f"scene_{i}_audio.mp3"
        duration = scene.audio.duration_seconds if scene.audio else 0.0
        lines.append(f"        # Scene {i}: {scene.description}")
        lines.append(f"        _t0_{i} = self.renderer.time")
        lines.append(f'        self.add_sound("{audio_path}")')
        for code_line in prepared_code.splitlines():
            lines.append(f"        {code_line}")
        # Program-injected: pad remaining time to match audio duration
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
