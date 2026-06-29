# Remotion 渲染引擎实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `RemotionRenderEngine`，将 AI 生成的 JSX 代码片段合成 Remotion 视频，与现有 `ManimRenderEngine` 并列运行。

**Architecture:** Python 生成完整 `VideoScene.tsx`（所有场景用 IIFE 包裹嵌入 `<Sequence>`），复制模板文件到 tmpdir 并 symlink `node_modules`，subprocess 调用 `node_modules/.bin/remotion render`。

**Tech Stack:** Python 3.12, Remotion 4, React 18, TypeScript 5, pnpm

## Global Constraints

- `node_modules` 不提交 git（`.gitignore` 排除）；pnpm 预装，随 Docker 镜像打包
- 画布固定 1280×720，fps 固定 30
- 超时默认 600 秒（`REMOTION_TIMEOUT_SECONDS`）
- `validate_code()` 保留接口，实现返回 `True, ""`
- `_RenderResultWithBytes` 子类与 Manim 引擎共享（直接从 `manim.py` import）
- 测试命令：`/Users/peng/.local/bin/uv run pytest tests/ -v`（在 `backend/` 目录下运行）
- Node 路径：`PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH"`

---

### Task 1：remotion-template 项目骨架

**Files:**
- Create: `remotion-template/package.json`
- Create: `remotion-template/tsconfig.json`
- Create: `remotion-template/remotion.config.ts`
- Create: `remotion-template/src/index.tsx`
- Create: `remotion-template/src/Root.tsx`
- Create: `remotion-template/src/VideoScene.tsx`（占位文件）
- Create: `remotion-template/.gitignore`

**Interfaces:**
- Produces: `remotion-template/node_modules/.bin/remotion` 可执行文件（Task 3 的 `health_check()` 检测此路径）

- [ ] **Step 1: 创建 `remotion-template/package.json`**

```json
{
  "name": "remotion-template",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "render": "remotion render"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "remotion": "^4.0.290"
  },
  "devDependencies": {
    "@remotion/cli": "^4.0.290",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "typescript": "^5.6.3"
  }
}
```

- [ ] **Step 2: 创建 `remotion-template/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: 创建 `remotion-template/remotion.config.ts`**

```ts
import { Config } from "@remotion/cli/config";
Config.setEntryPoint("./src/index.tsx");
```

- [ ] **Step 4: 创建 `remotion-template/src/index.tsx`**

```tsx
import { registerRoot } from "remotion";
import { Root } from "./Root";
registerRoot(Root);
```

- [ ] **Step 5: 创建 `remotion-template/src/Root.tsx`**

```tsx
import { Composition } from "remotion";
import { VideoScene, totalFrames } from "./VideoScene";

export const Root: React.FC = () => (
  <Composition
    id="VideoScene"
    component={VideoScene}
    durationInFrames={totalFrames}
    fps={30}
    width={1280}
    height={720}
  />
);
```

注意 Root.tsx 顶部需要 `import React from "react";`（或确认 tsconfig 开启了 `jsx: react-jsx`，则不需要显式 import）。由于 tsconfig 已设 `"jsx": "react-jsx"`，不需要显式 import React。

- [ ] **Step 6: 创建占位 `remotion-template/src/VideoScene.tsx`**

此文件让模板本身可以通过 TS 检查；实际渲染时 Python 在 tmpdir 写入真实内容。

```tsx
import { AbsoluteFill } from "remotion";

export const totalFrames = 30;

export const VideoScene: React.FC = () => (
  <AbsoluteFill style={{ background: "#F7F3FF" }} />
);
```

- [ ] **Step 7: 创建 `remotion-template/.gitignore`**

```
node_modules/
```

- [ ] **Step 8: 安装依赖**

```bash
cd remotion-template
PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm install
```

预期输出：`Done in ...s`，`node_modules/.bin/remotion` 文件存在。

- [ ] **Step 9: 验证模板可执行**

```bash
cd remotion-template
PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" node_modules/.bin/remotion --version
```

预期输出：打印 Remotion 版本号，exit code 0。

- [ ] **Step 10: Commit**

```bash
git add remotion-template/package.json remotion-template/tsconfig.json \
        remotion-template/remotion.config.ts remotion-template/src/ \
        remotion-template/.gitignore
git commit -m "feat: add remotion-template project skeleton"
```

---

### Task 2：`_build_remotion_tsx()` 函数 + 单元测试

**Files:**
- Create: `backend/app/engines/render/remotion.py`
- Create: `backend/tests/test_remotion_render_engine.py`

**Interfaces:**
- Consumes: `SceneInput`, `SceneAudio` from `app.engines.render.base`
- Produces:
  - `_build_remotion_tsx(scenes: list[SceneInput], fps: int = 30) -> str`：返回完整 `VideoScene.tsx` 字符串
  - `RemotionRenderEngine`（空壳，Task 3 填充 `render()`）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_remotion_render_engine.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_remotion_render_engine.py -v
```

预期：`ModuleNotFoundError: No module named 'app.engines.render.remotion'`

- [ ] **Step 3: 实现 `_build_remotion_tsx()` 和 `RemotionRenderEngine` 空壳**

新建 `backend/app/engines/render/remotion.py`：

```python
import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path

from app.config import settings
from app.engines.render.base import RenderEngine, RenderRequest, RenderResult, SceneInput
from app.engines.render.manim import _RenderResultWithBytes

logger = logging.getLogger(__name__)

_REMOTION_IMPORTS = """\
import React from 'react';
import {
  AbsoluteFill, Sequence, Audio,
  useCurrentFrame, useVideoConfig,
  interpolate, spring,
} from 'remotion';
"""


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
        template_dir = Path(settings.REMOTION_TEMPLATE_DIR)
        remotion_bin = template_dir / "node_modules" / ".bin" / "remotion"
        return remotion_bin.exists()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_remotion_render_engine.py -v
```

预期：所有 6 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/render/remotion.py backend/tests/test_remotion_render_engine.py
git commit -m "feat: add _build_remotion_tsx() and RemotionRenderEngine stub"
```

---

### Task 3：`RemotionRenderEngine.render()` + config + factory + worker 日志

**Files:**
- Modify: `backend/app/engines/render/remotion.py`（填充 `render()`）
- Modify: `backend/app/config.py`（新增 `REMOTION_TIMEOUT_SECONDS`、`REMOTION_TEMPLATE_DIR`）
- Modify: `backend/app/engines/render/factory.py`（加 remotion 分支）
- Modify: `backend/app/workers/render_worker.py`（日志 hardcode 修正）
- Modify: `backend/tests/test_remotion_render_engine.py`（追加 render 集成测试）

**Interfaces:**
- Consumes:
  - `_build_remotion_tsx(scenes, fps)` from Task 2
  - `settings.REMOTION_TIMEOUT_SECONDS: float`
  - `settings.REMOTION_TEMPLATE_DIR: str`
  - `_RenderResultWithBytes` from `app.engines.render.manim`
- Produces:
  - `get_render_engine("remotion")` → `RemotionRenderEngine()`（factory）
  - `RemotionRenderEngine.render(request, work_dir)` → `RenderResult`

- [ ] **Step 1: 新增 config 字段**

在 `backend/app/config.py` 的 `Settings` 类中，紧跟 `MANIM_TIMEOUT_SECONDS` 后添加：

```python
    REMOTION_TIMEOUT_SECONDS: float = 600.0
    REMOTION_TEMPLATE_DIR: str = "remotion-template"
```

- [ ] **Step 2: 写失败的 render 测试**

在 `backend/tests/test_remotion_render_engine.py` 末尾追加：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.render.base import RenderRequest, SceneAudio


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
         patch("pathlib.Path.read_bytes", return_value=fake_video_bytes):
        result = await engine.render(request)

    assert result.success is True
    assert result.video_bytes == fake_video_bytes
    assert "Rendering..." in result.render_log


def _async_line_iter(lines: list[bytes]):
    async def _gen():
        for line in lines:
            yield line
    return _gen()


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

    with patch("asyncio.create_subprocess_exec", return_value=fake_proc):
        result = await engine.render(request)

    assert result.success is False
    assert "exited with code 1" in result.error_message
```

- [ ] **Step 3: 运行新测试，确认失败**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_remotion_render_engine.py::test_remotion_render_engine_success -v
```

预期：`NotImplementedError: render() will be implemented in Task 3`

- [ ] **Step 4: 实现 `RemotionRenderEngine.render()`**

将 `backend/app/engines/render/remotion.py` 中 `render()` 替换为：

```python
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
```

同时在文件末尾添加 `_find_output_video` 辅助函数（与 Manim 引擎中相同逻辑）：

```python
def _find_output_video(tmpdir: str, expected_path: str) -> str | None:
    if os.path.exists(expected_path):
        return expected_path
    for root, _, files in os.walk(tmpdir):
        for fname in files:
            if fname.endswith(".mp4"):
                return os.path.join(root, fname)
    return None
```

- [ ] **Step 5: 更新 `factory.py`**

将 `backend/app/engines/render/factory.py` 替换为：

```python
from app.engines.render.manim import ManimRenderEngine
from app.engines.render.remotion import RemotionRenderEngine


def get_render_engine(engine_name: str = "manim"):
    if engine_name == "manim":
        return ManimRenderEngine()
    if engine_name == "remotion":
        return RemotionRenderEngine()
    raise ValueError(f"Unknown render engine: {engine_name}")
```

- [ ] **Step 6: 修正 `render_worker.py` 日志**

将 `backend/app/workers/render_worker.py` 第 63 行：

```python
        logger.info("[RenderWorker] Starting Manim render for asset %s", asset_id_str)
```

改为：

```python
        logger.info("[RenderWorker] Starting %s render for asset %s", render_engine_name, asset_id_str)
```

- [ ] **Step 7: 运行全部 remotion 测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_remotion_render_engine.py -v
```

预期：所有测试 PASS。

- [ ] **Step 8: 运行全套测试，确认无回归**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS（无新增失败）。

- [ ] **Step 9: Commit**

```bash
git add backend/app/engines/render/remotion.py \
        backend/app/config.py \
        backend/app/engines/render/factory.py \
        backend/app/workers/render_worker.py \
        backend/tests/test_remotion_render_engine.py
git commit -m "feat: implement RemotionRenderEngine with subprocess render"
```
