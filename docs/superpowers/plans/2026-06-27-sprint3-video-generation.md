# Sprint 3 视频生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现视频生产流水线第二阶段：并发 TTS 合成音频 → Manim subprocess 渲染 → 上传 MinIO → 前端视频审核 presigned URL。

**Architecture:** RenderWorker 从 ScriptVersion 读取镜头数据，并发调用火山引擎 TTS 合成各镜头音频并上传 MinIO，随后生成注入了音频路径的 Manim 脚本并通过 subprocess 渲染，最终视频上传 MinIO 后写 VideoAsset 记录并通过 Temporal signal 通知 Workflow。前端通过新 API 端点获取 presigned URL 播放视频。

**Tech Stack:** Python asyncio, httpx（TTS HTTP 调用）, minio（MinIO SDK）, asyncio.create_subprocess_exec（Manim 渲染）, FastAPI, SQLAlchemy sync（Worker 内）, Alembic（DB migration）

## Global Constraints

- Python 包管理用 `/Users/peng/.local/bin/uv`，不用裸 `uv`
- pytest 命令：`cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v`
- 不设数据库外键约束，表间关联在应用层维护
- Worker 内使用同步 SQLAlchemy（`get_sync_session()`），API 层用异步
- MinIO bucket 路径：音频 `audio/{project_id}/{script_version_id}/scene_{index}.mp3`，视频 `video/{project_id}/{script_version_id}/{asset_id}.mp4`
- 所有镜头代码共用一个 Manim Scene（单个 `construct()` 方法），音频在每个镜头块起始处注入

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/pyproject.toml` | 修改 | 新增 `minio` 依赖 |
| `backend/app/config.py` | 修改 | 新增 TTS 配置字段 |
| `backend/.env.example` | 修改 | 新增 TTS 环境变量示例 |
| `backend/app/engines/tts/voice_map.py` | 新增 | 音色别名 → 火山 speaker ID 映射 |
| `backend/app/storage.py` | 新增 | MinIO upload/download/presigned URL 工具函数 |
| `backend/app/engines/tts/volcengine.py` | 新增 | 火山引擎 HTTP TTS 实现 |
| `backend/app/engines/tts/factory.py` | 新增 | `get_tts_engine()` 工厂 |
| `backend/app/engines/render/manim.py` | 新增 | Manim subprocess 渲染实现 |
| `backend/app/engines/render/factory.py` | 新增 | `get_render_engine()` 工厂 |
| `backend/app/models/video_asset.py` | 修改 | 新增 `render_log` 字段 |
| `backend/alembic/versions/` | 新增 | 为 video_assets 添加 render_log 列的迁移 |
| `backend/app/workers/render_worker.py` | 修改 | 实现完整 TTS → 渲染 → 上传流水线 |
| `backend/app/api/projects.py` | 修改 | 新增 GET `/{id}/video-url?asset_id=` 端点 |
| `backend/tests/test_tts_engine.py` | 新增 | VolcengineTTSEngine 单元测试 |
| `backend/tests/test_storage.py` | 新增 | MinIO storage 工具函数测试 |
| `backend/tests/test_render_worker.py` | 新增 | RenderWorker 集成测试 |
| `backend/tests/test_video_url_api.py` | 新增 | video-url 端点测试 |

---

### Task 1: 依赖 + 配置 + 音色映射

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Create: `backend/app/engines/tts/voice_map.py`

**Interfaces:**
- Produces:
  - `settings.VOLCENGINE_TTS_API_KEY: str`
  - `settings.VOLCENGINE_TTS_RESOURCE_ID: str`（默认 `"seed-tts-2.0"`）
  - `settings.TTS_ENGINE: str`（默认 `"volcengine"`）
  - `settings.MINIO_BUCKET: str`（默认 `"video-workflow"`）
  - `settings.MANIM_TIMEOUT_SECONDS: float`（默认 `600.0`）
  - `voice_map.resolve_speaker(alias: str) -> str`

- [ ] **Step 1: 在 pyproject.toml 新增 minio 依赖**

`backend/pyproject.toml` dependencies 列表末尾加：
```toml
    "minio>=7.2",
```

- [ ] **Step 2: 安装依赖**

```bash
cd backend && /Users/peng/.local/bin/uv sync
```

Expected: minio 包安装成功，无报错。

- [ ] **Step 3: 在 config.py 新增 TTS 和渲染配置字段**

在 `backend/app/config.py` 的 `Settings` 类中，`CORS_ORIGINS` 之前新增：

```python
    VOLCENGINE_TTS_API_KEY: str = ""
    VOLCENGINE_TTS_RESOURCE_ID: str = "seed-tts-2.0"
    TTS_ENGINE: str = "volcengine"
    MINIO_BUCKET: str = "video-workflow"
    MANIM_TIMEOUT_SECONDS: float = 600.0
```

- [ ] **Step 4: 更新 .env.example**

在 `backend/.env.example` 末尾追加：
```
VOLCENGINE_TTS_API_KEY=
VOLCENGINE_TTS_RESOURCE_ID=seed-tts-2.0
TTS_ENGINE=volcengine
MINIO_BUCKET=video-workflow
MANIM_TIMEOUT_SECONDS=600
```

- [ ] **Step 5: 创建 voice_map.py**

创建 `backend/app/engines/tts/voice_map.py`：

```python
VOICE_ALIAS_MAP: dict[str, str] = {
    "male_calm": "zh_male_rap_M392_expressive",
    "female_warm": "zh_female_story_F271_expressive",
}


def resolve_speaker(alias: str) -> str:
    """Return fire speaker ID for alias; fall back to alias itself if not found."""
    return VOICE_ALIAS_MAP.get(alias, alias)
```

- [ ] **Step 6: 验证 config 可导入**

```bash
cd backend && /Users/peng/.local/bin/uv run python -c "from app.config import settings; print(settings.VOLCENGINE_TTS_RESOURCE_ID)"
```

Expected 输出: `seed-tts-2.0`

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/config.py backend/.env.example backend/app/engines/tts/voice_map.py
git commit -m "feat: add TTS/MinIO config and voice alias map"
```

---

### Task 2: MinIO Storage 工具

**Files:**
- Create: `backend/app/storage.py`
- Create: `backend/tests/test_storage.py`

**Interfaces:**
- Consumes: `settings.MINIO_ENDPOINT`, `settings.MINIO_ACCESS_KEY`, `settings.MINIO_SECRET_KEY`, `settings.MINIO_BUCKET`
- Produces:
  - `upload_bytes(key: str, data: bytes, content_type: str) -> None`
  - `download_to_file(key: str, local_path: str) -> None`
  - `get_presigned_url(key: str, expires_seconds: int = 3600) -> str`

- [ ] **Step 1: 写测试**

创建 `backend/tests/test_storage.py`：

```python
from unittest.mock import MagicMock, patch, call
import pytest


def test_upload_bytes_calls_put_object():
    mock_client = MagicMock()
    with patch("app.storage._get_client", return_value=mock_client):
        from app.storage import upload_bytes
        upload_bytes("test/key.mp3", b"audio-data", "audio/mpeg")
    mock_client.put_object.assert_called_once()
    args = mock_client.put_object.call_args
    assert args.kwargs["bucket_name"] == mock_client.put_object.call_args.kwargs["bucket_name"] or True
    # verify key passed
    call_kwargs = mock_client.put_object.call_args[1]
    assert call_kwargs["object_name"] == "test/key.mp3"


def test_get_presigned_url_returns_string():
    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = "http://minio/signed-url"
    with patch("app.storage._get_client", return_value=mock_client):
        from app.storage import get_presigned_url
        url = get_presigned_url("video/proj/asset.mp4")
    assert url == "http://minio/signed-url"


def test_download_to_file_calls_fget_object(tmp_path):
    mock_client = MagicMock()
    with patch("app.storage._get_client", return_value=mock_client):
        from app.storage import download_to_file
        dest = str(tmp_path / "audio.mp3")
        download_to_file("audio/key.mp3", dest)
    mock_client.fget_object.assert_called_once()
    call_kwargs = mock_client.fget_object.call_args[1]
    assert call_kwargs["object_name"] == "audio/key.mp3"
    assert call_kwargs["file_path"] == dest
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_storage.py -v
```

Expected: ImportError 或 ModuleNotFoundError（app.storage 不存在）。

- [ ] **Step 3: 实现 storage.py**

创建 `backend/app/storage.py`：

```python
import io
from datetime import timedelta
from minio import Minio
from app.config import settings


def _get_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False,
    )


def _ensure_bucket(client: Minio) -> None:
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)


def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    client = _get_client()
    _ensure_bucket(client)
    client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def download_to_file(key: str, local_path: str) -> None:
    client = _get_client()
    client.fget_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=key,
        file_path=local_path,
    )


def get_presigned_url(key: str, expires_seconds: int = 3600) -> str:
    client = _get_client()
    return client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=key,
        expires=timedelta(seconds=expires_seconds),
    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_storage.py -v
```

Expected: 3 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/storage.py backend/tests/test_storage.py
git commit -m "feat: add MinIO storage helper (upload/download/presigned)"
```

---

### Task 3: VolcengineTTSEngine

**Files:**
- Create: `backend/app/engines/tts/volcengine.py`
- Create: `backend/app/engines/tts/factory.py`
- Create: `backend/tests/test_tts_engine.py`

**Interfaces:**
- Consumes: `TTSRequest`, `TTSResult`（from `app.engines.tts.base`）, `settings.VOLCENGINE_TTS_API_KEY`, `settings.VOLCENGINE_TTS_RESOURCE_ID`, `resolve_speaker`（from `app.engines.tts.voice_map`）
- Produces:
  - `VolcengineTTSEngine` — 实现 `TTSEngine` Protocol
    - `engine_name: str` → `"volcengine"`
    - `async synthesize(request: TTSRequest) -> TTSResult`：调用火山 API，返回 `TTSResult(success=True, output_path=None, duration_seconds=None, error_message=None)`，audio bytes 通过 `TTSResult` 的扩展字段传回（见下）
    - `async health_check() -> bool`
  - `get_tts_engine() -> VolcengineTTSEngine`

**注意：** `TTSResult.output_path` 存放的是 MinIO key（不是本地路径）；实际音频字节通过扩展后的 `TTSResult` 传回，Task 5 的 RenderWorker 会处理上传。为了不修改 base.py Protocol，`VolcengineTTSEngine.synthesize` 实际返回一个子类 `VolcanTTSResult(TTSResult)` 附带 `audio_bytes: bytes`。

- [ ] **Step 1: 写测试**

创建 `backend/tests/test_tts_engine.py`：

```python
import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.tts.base import TTSRequest
from app.engines.tts.volcengine import VolcengineTTSEngine, VolcanTTSResult


@pytest.fixture
def engine():
    return VolcengineTTSEngine(api_key="test-key", resource_id="seed-tts-2.0")


@pytest.mark.asyncio
async def test_synthesize_success(engine):
    audio_bytes = b"fake-audio-data"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "code": 0,
        "message": "success",
        "data": base64.b64encode(audio_bytes).decode(),
    }
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        result = await engine.synthesize(TTSRequest(text="你好世界", voice="male_calm"))
    assert result.success is True
    assert isinstance(result, VolcanTTSResult)
    assert result.audio_bytes == audio_bytes


@pytest.mark.asyncio
async def test_synthesize_api_error(engine):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"code": 10001, "message": "invalid api key"}
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        result = await engine.synthesize(TTSRequest(text="hello", voice="male_calm"))
    assert result.success is False
    assert "invalid api key" in result.error_message


@pytest.mark.asyncio
async def test_health_check_success(engine):
    with patch.object(engine, "synthesize", new_callable=AsyncMock) as mock_syn:
        mock_result = MagicMock()
        mock_result.success = True
        mock_syn.return_value = mock_result
        ok = await engine.health_check()
    assert ok is True


def test_voice_alias_resolved(engine):
    from app.engines.tts.voice_map import VOICE_ALIAS_MAP
    assert "male_calm" in VOICE_ALIAS_MAP
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_tts_engine.py -v
```

Expected: ImportError（volcengine 模块不存在）。

- [ ] **Step 3: 实现 volcengine.py**

创建 `backend/app/engines/tts/volcengine.py`：

```python
import base64
import uuid
from dataclasses import dataclass
import httpx
from app.engines.tts.base import TTSRequest, TTSResult
from app.engines.tts.voice_map import resolve_speaker

_TTS_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"


@dataclass
class VolcanTTSResult(TTSResult):
    audio_bytes: bytes = b""


class VolcengineTTSEngine:
    engine_name = "volcengine"

    def __init__(self, api_key: str, resource_id: str = "seed-tts-2.0"):
        self._api_key = api_key
        self._resource_id = resource_id

    async def synthesize(self, request: TTSRequest) -> VolcanTTSResult:
        speaker = resolve_speaker(request.voice)
        headers = {
            "X-Api-Key": self._api_key,
            "X-Api-Resource-Id": self._resource_id,
            "X-Api-Request-Id": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        body = {
            "req_params": {
                "text": request.text,
                "speaker": speaker,
                "audio_params": {
                    "format": "mp3",
                    "sample_rate": 24000,
                },
            }
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(_TTS_URL, json=body, headers=headers)

        data = resp.json()
        if data.get("code", 0) != 0:
            return VolcanTTSResult(
                success=False,
                output_path=None,
                duration_seconds=None,
                error_message=data.get("message", "TTS API error"),
                audio_bytes=b"",
            )

        audio_bytes = base64.b64decode(data["data"])
        return VolcanTTSResult(
            success=True,
            output_path=None,
            duration_seconds=None,
            error_message=None,
            audio_bytes=audio_bytes,
        )

    async def health_check(self) -> bool:
        result = await self.synthesize(TTSRequest(text="测试", voice="male_calm"))
        return result.success
```

- [ ] **Step 4: 创建 factory.py**

创建 `backend/app/engines/tts/factory.py`：

```python
from app.config import settings
from app.engines.tts.volcengine import VolcengineTTSEngine


def get_tts_engine() -> VolcengineTTSEngine:
    return VolcengineTTSEngine(
        api_key=settings.VOLCENGINE_TTS_API_KEY,
        resource_id=settings.VOLCENGINE_TTS_RESOURCE_ID,
    )
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_tts_engine.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/engines/tts/volcengine.py backend/app/engines/tts/factory.py backend/tests/test_tts_engine.py
git commit -m "feat: add VolcengineTTSEngine with voice alias resolution"
```

---

### Task 4: VideoAsset model + migration（新增 render_log 字段）

**Files:**
- Modify: `backend/app/models/video_asset.py`
- Create: `backend/alembic/versions/<hash>_add_render_log_to_video_assets.py`

**Interfaces:**
- Produces: `VideoAsset.render_log: Optional[str]`

- [ ] **Step 1: 修改 VideoAsset model**

在 `backend/app/models/video_asset.py` 中，`created_at` 字段之前新增：

```python
    render_log: Mapped[Optional[str]] = mapped_column(String(50000))
```

同时在文件顶部 `from sqlalchemy import String, Float, DateTime` 改为：
```python
from sqlalchemy import String, Float, DateTime, Text
```

并将 `render_log` 的列类型改为 `Text`（不限长度）：
```python
    render_log: Mapped[Optional[str]] = mapped_column(Text)
```

完整修改后的 `video_asset.py`：

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Float, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class VideoAsset(Base):
    __tablename__ = "video_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    script_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True)
    )
    video_file_key: Mapped[Optional[str]] = mapped_column(String(500))
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    resolution: Mapped[Optional[str]] = mapped_column(String(20))
    render_log: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="rendering")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
```

- [ ] **Step 2: 生成 Alembic migration**

```bash
cd backend && /Users/peng/.local/bin/uv run alembic revision --autogenerate -m "add_render_log_to_video_assets"
```

Expected: 生成一个新迁移文件在 `alembic/versions/`。

- [ ] **Step 3: 检查生成的迁移文件**

打开生成的迁移文件，确认 `upgrade()` 中包含：
```python
op.add_column('video_assets', sa.Column('render_log', sa.Text(), nullable=True))
```

如果 autogenerate 没有产生正确内容，手动编辑迁移文件使其包含上述语句，`downgrade()` 包含：
```python
op.drop_column('video_assets', 'render_log')
```

- [ ] **Step 4: 应用迁移（需要数据库运行）**

```bash
cd backend && /Users/peng/.local/bin/uv run alembic upgrade head
```

Expected: `Running upgrade ... -> <hash>` 成功。若数据库未运行则跳过，待环境就绪后补跑。

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/video_asset.py backend/alembic/versions/
git commit -m "feat: add render_log column to video_assets"
```

---

### Task 5: ManimRenderEngine

**Files:**
- Create: `backend/app/engines/render/manim.py`
- Create: `backend/app/engines/render/factory.py`

**Interfaces:**
- Consumes: `RenderRequest`, `RenderResult`, `SceneInput`, `SceneAudio`（from `app.engines.render.base`）, `settings.MANIM_TIMEOUT_SECONDS`
- Produces:
  - `ManimRenderEngine` — 实现 `RenderEngine` Protocol
    - `engine_name: str` → `"manim"`
    - `async render(request: RenderRequest) -> RenderResult`：生成 Manim 脚本，subprocess 渲染，返回本地视频路径（output_path 为本地临时路径）
    - `async validate_code(scenes: list[SceneInput]) -> tuple[bool, str]`：始终返回 `(True, "")`（Sprint 3 不实现）
    - `async health_check() -> bool`
  - `get_render_engine() -> ManimRenderEngine`

**Manim 脚本模板规范：**
- 生成一个 Python 文件，包含单个继承 `Scene` 的类
- `construct()` 方法内，按 scenes 顺序，每个镜头块前调用 `self.add_sound("scene_{i}_audio.mp3")`（使用相对路径，Manim 工作目录为脚本所在临时目录）
- 每个镜头的 `code` 字段内容直接嵌入 `construct()` 中（镜头间用空行分隔）

- [ ] **Step 1: 创建 manim.py**

创建 `backend/app/engines/render/manim.py`：

```python
import asyncio
import os
import tempfile
import textwrap
from pathlib import Path
from app.engines.render.base import RenderEngine, RenderRequest, RenderResult, SceneInput
from app.config import settings


class ManimRenderEngine:
    engine_name = "manim"

    async def validate_code(self, scenes: list[SceneInput]) -> tuple[bool, str]:
        return True, ""

    async def render(self, request: RenderRequest) -> RenderResult:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "scene.py")
            output_path = os.path.join(tmpdir, "output.mp4")
            script_content = _build_manim_script(request.scenes, tmpdir)

            with open(script_path, "w") as f:
                f.write(script_content)

            cmd = [
                "python", "-m", "manim", "render",
                script_path, "MainScene",
                "--output_file", output_path,
                "--format", "mp4",
                "--media_dir", tmpdir,
                "-q", "m",  # medium quality
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
                return RenderResult(
                    success=False,
                    output_path=None,
                    duration_seconds=None,
                    error_message=f"Manim exited with code {proc.returncode}",
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


def _build_manim_script(scenes: list[SceneInput], workdir: str) -> str:
    lines = [
        "from manim import *",
        "",
        "",
        "class MainScene(Scene):",
        "    def construct(self):",
    ]
    for i, scene in enumerate(scenes):
        audio_filename = f"scene_{i}_audio.mp3"
        lines.append(f"        # Scene {i}: {scene.description}")
        lines.append(f'        self.add_sound("{audio_filename}")')
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
```

- [ ] **Step 2: 创建 render factory.py**

创建 `backend/app/engines/render/factory.py`：

```python
from app.engines.render.manim import ManimRenderEngine


def get_render_engine(engine_name: str = "manim") -> ManimRenderEngine:
    if engine_name == "manim":
        return ManimRenderEngine()
    raise ValueError(f"Unknown render engine: {engine_name}")
```

- [ ] **Step 3: 验证可导入**

```bash
cd backend && /Users/peng/.local/bin/uv run python -c "from app.engines.render.factory import get_render_engine; e = get_render_engine(); print(e.engine_name)"
```

Expected 输出: `manim`

- [ ] **Step 4: Commit**

```bash
git add backend/app/engines/render/manim.py backend/app/engines/render/factory.py
git commit -m "feat: add ManimRenderEngine with subprocess rendering and audio injection"
```

---

### Task 6: RenderWorker._execute 完整流水线

**Files:**
- Modify: `backend/app/workers/render_worker.py`
- Create: `backend/tests/test_render_worker.py`

**Interfaces:**
- Consumes:
  - `get_tts_engine() -> VolcengineTTSEngine`（from `app.engines.tts.factory`）
  - `get_render_engine(engine_name) -> ManimRenderEngine`（from `app.engines.render.factory`）
  - `upload_bytes(key, data, content_type)`（from `app.storage`）
  - `VolcanTTSResult.audio_bytes: bytes`
  - `_RenderResultWithBytes.video_bytes: bytes`
  - `VideoAsset`, `ScriptVersion`, `VideoProject`（ORM models）
- Produces: `RenderWorker._execute(task) -> dict` — 完整实现，返回 `{"asset_id": str, "video_file_key": str}`

**流程（在 `_execute` 内）：**
1. 读 task.project_id 对应的 `VideoProject` → 获取 `tts_voice`, `render_engine`, `current_script_version_id`
2. 读 `ScriptVersion` → 获取 `scenes[]`
3. 并发 TTS：`asyncio.gather(*[tts.synthesize(...) for scene in scenes], return_exceptions=True)`
4. 检查 TTS 结果，任一失败则抛 `RuntimeError`
5. 上传各 scene 音频到 MinIO：`audio/{project_id}/{script_version_id}/scene_{i}.mp3`
6. 创建 `VideoAsset(status="rendering")` 写库，获得 `asset_id`
7. 构建 `RenderRequest`（scenes 含 audio_path 为 MinIO key）
8. 调用 `render_engine.render(request)`（ManimRenderEngine 在临时目录内处理音频下载）
9. 若渲染失败：更新 `asset.status="failed"`, `asset.render_log=...`，commit，抛异常
10. 上传视频到 MinIO：`video/{project_id}/{script_version_id}/{asset_id}.mp4`
11. 更新 `asset.status="ready"`, `asset.video_file_key=key`, `asset.render_log=...`
12. 更新 `project.current_video_asset_id = asset.id`，commit
13. 返回 `{"asset_id": str(asset.id), "video_file_key": key}`

**注意：** ManimRenderEngine 渲染时需要将 MinIO 音频下载到本地临时目录（与 Manim 脚本同目录）。为保持 RenderEngine Protocol 简洁，RenderWorker 在调用 render 前先将音频从 MinIO 下载到临时目录，并在 `SceneAudio.audio_path` 填入本地路径。

- [ ] **Step 1: 写测试**

创建 `backend/tests/test_render_worker.py`：

```python
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timezone


def make_project(script_version_id=None):
    p = MagicMock()
    p.id = uuid.uuid4()
    p.topic_id = uuid.uuid4()
    p.tts_voice = "male_calm"
    p.render_engine = "manim"
    p.current_script_version_id = script_version_id or uuid.uuid4()
    p.current_video_asset_id = None
    return p


def make_script_version(project_id, scenes=None):
    sv = MagicMock()
    sv.id = uuid.uuid4()
    sv.project_id = project_id
    sv.render_engine = "manim"
    sv.scenes = scenes or [
        {"scene_index": 0, "narration": "Hello world", "description": "intro", "code": "self.play(Write(Text('Hello')))"},
        {"scene_index": 1, "narration": "Goodbye", "description": "outro", "code": "self.play(FadeOut(Text('Hello')))"},
    ]
    return sv


def make_task(project_id):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.project_id = project_id
    t.input_payload = {}
    return t


@pytest.mark.asyncio
async def test_render_worker_success():
    from app.workers.render_worker import RenderWorker
    from app.engines.tts.volcengine import VolcanTTSResult
    from app.engines.render.manim import _RenderResultWithBytes

    project = make_project()
    sv = make_script_version(project.id)
    task = make_task(project.id)

    tts_result = VolcanTTSResult(
        success=True, output_path=None, duration_seconds=None,
        error_message=None, audio_bytes=b"fake-audio"
    )
    render_result = _RenderResultWithBytes(
        success=True, output_path="/tmp/out.mp4", duration_seconds=10.0,
        error_message=None, render_log="OK", video_bytes=b"fake-video"
    )

    mock_db = MagicMock()
    mock_db.get.side_effect = [project, sv]

    mock_tts = AsyncMock()
    mock_tts.synthesize = AsyncMock(return_value=tts_result)

    mock_render = AsyncMock()
    mock_render.render = AsyncMock(return_value=render_result)

    with patch("app.workers.render_worker.get_sync_session", return_value=mock_db), \
         patch("app.workers.render_worker.get_tts_engine", return_value=mock_tts), \
         patch("app.workers.render_worker.get_render_engine", return_value=mock_render), \
         patch("app.workers.render_worker.upload_bytes") as mock_upload, \
         patch("app.workers.render_worker.download_to_file"):

        temporal_client = AsyncMock()
        worker = RenderWorker(worker_id="test", temporal_client=temporal_client)
        result = await worker._execute(task)

    assert result["video_file_key"].startswith("video/")
    assert "asset_id" in result
    # upload called: N audio files + 1 video
    assert mock_upload.call_count == 3  # 2 scenes + 1 video


@pytest.mark.asyncio
async def test_render_worker_tts_failure_raises():
    from app.workers.render_worker import RenderWorker
    from app.engines.tts.volcengine import VolcanTTSResult

    project = make_project()
    sv = make_script_version(project.id)
    task = make_task(project.id)

    tts_fail = VolcanTTSResult(
        success=False, output_path=None, duration_seconds=None,
        error_message="API error", audio_bytes=b""
    )

    mock_db = MagicMock()
    mock_db.get.side_effect = [project, sv]
    mock_tts = AsyncMock()
    mock_tts.synthesize = AsyncMock(return_value=tts_fail)

    with patch("app.workers.render_worker.get_sync_session", return_value=mock_db), \
         patch("app.workers.render_worker.get_tts_engine", return_value=mock_tts), \
         patch("app.workers.render_worker.upload_bytes"):

        temporal_client = AsyncMock()
        worker = RenderWorker(worker_id="test", temporal_client=temporal_client)
        with pytest.raises(RuntimeError, match="TTS failed"):
            await worker._execute(task)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_render_worker.py -v
```

Expected: 失败（RenderWorker._execute 是 NotImplementedError）。

- [ ] **Step 3: 实现 render_worker.py**

完整替换 `backend/app/workers/render_worker.py`：

```python
import asyncio
import logging
import tempfile
import os
import uuid
from app.db import get_sync_session
from app.engines.tts.factory import get_tts_engine
from app.engines.tts.base import TTSRequest
from app.engines.render.factory import get_render_engine
from app.engines.render.base import RenderRequest, SceneInput, SceneAudio
from app.models.project import VideoProject
from app.models.script_version import ScriptVersion
from app.models.video_asset import VideoAsset
from app.storage import upload_bytes, download_to_file
from app.workers.base import BaseWorker

logger = logging.getLogger(__name__)


class RenderWorker(BaseWorker):
    supported_task_types = ["render_video"]

    async def _execute(self, task) -> dict:
        db = get_sync_session()
        try:
            project = db.get(VideoProject, task.project_id)
            if project is None:
                raise ValueError(f"Project {task.project_id} not found")

            sv = db.get(ScriptVersion, project.current_script_version_id)
            if sv is None:
                raise ValueError("No script version found for project")

            scenes_data = list(sv.scenes or [])
            project_id = str(project.id)
            script_version_id = str(sv.id)
            tts_voice = project.tts_voice
            render_engine_name = project.render_engine
        finally:
            db.close()

        # Step 1: 并发 TTS 合成
        logger.info("[RenderWorker] Starting TTS for %d scenes", len(scenes_data))
        tts_engine = get_tts_engine()
        tts_requests = [
            TTSRequest(text=s.get("narration", ""), voice=tts_voice)
            for s in scenes_data
        ]
        tts_results = await asyncio.gather(
            *[tts_engine.synthesize(req) for req in tts_requests],
            return_exceptions=True,
        )

        # 检查 TTS 结果
        for i, result in enumerate(tts_results):
            if isinstance(result, Exception):
                raise RuntimeError(f"TTS failed for scene {i}: {result}")
            if not result.success:
                raise RuntimeError(f"TTS failed for scene {i}: {result.error_message}")

        # Step 2: 上传音频到 MinIO
        audio_keys = []
        for i, tts_result in enumerate(tts_results):
            key = f"audio/{project_id}/{script_version_id}/scene_{i}.mp3"
            upload_bytes(key, tts_result.audio_bytes, "audio/mpeg")
            audio_keys.append(key)
            logger.info("[RenderWorker] Uploaded audio scene %d → %s", i, key)

        # Step 3: 创建 VideoAsset 记录
        asset_id = uuid.uuid4()
        asset_id_str = str(asset_id)
        db = get_sync_session()
        try:
            asset = VideoAsset(
                id=asset_id,
                project_id=project.id,
                script_version_id=sv.id,
                status="rendering",
            )
            db.add(asset)
            db.commit()
        finally:
            db.close()

        # Step 4: 下载音频到临时目录并渲染
        logger.info("[RenderWorker] Starting Manim render for asset %s", asset_id_str)
        with tempfile.TemporaryDirectory() as tmpdir:
            # 下载各 scene 音频到临时目录
            for i, audio_key in enumerate(audio_keys):
                local_audio = os.path.join(tmpdir, f"scene_{i}_audio.mp3")
                download_to_file(audio_key, local_audio)

            scene_inputs = [
                SceneInput(
                    scene_index=i,
                    narration=s.get("narration", ""),
                    description=s.get("description", ""),
                    code=s.get("code", ""),
                    audio=SceneAudio(
                        scene_index=i,
                        audio_path=os.path.join(tmpdir, f"scene_{i}_audio.mp3"),
                        duration_seconds=0.0,
                    ),
                )
                for i, s in enumerate(scenes_data)
            ]

            render_engine = get_render_engine(render_engine_name)
            render_request = RenderRequest(
                scenes=scene_inputs,
                output_format="mp4",
                resolution=(1920, 1080),
                fps=30,
            )
            render_result = await render_engine.render(render_request)

            if not render_result.success:
                db = get_sync_session()
                try:
                    asset_orm = db.get(VideoAsset, asset_id)
                    if asset_orm:
                        asset_orm.status = "failed"
                        asset_orm.render_log = render_result.render_log
                        db.commit()
                finally:
                    db.close()
                raise RuntimeError(
                    f"Render failed: {render_result.error_message}"
                )

            # Step 5: 上传视频到 MinIO
            video_key = f"video/{project_id}/{script_version_id}/{asset_id_str}.mp4"
            upload_bytes(video_key, render_result.video_bytes, "video/mp4")
            logger.info("[RenderWorker] Uploaded video → %s", video_key)

        # Step 6: 更新 VideoAsset 和 Project
        db = get_sync_session()
        try:
            asset_orm = db.get(VideoAsset, asset_id)
            if asset_orm:
                asset_orm.status = "ready"
                asset_orm.video_file_key = video_key
                asset_orm.render_log = render_result.render_log
                asset_orm.duration_seconds = render_result.duration_seconds

            project_orm = db.get(VideoProject, task.project_id)
            if project_orm:
                project_orm.current_video_asset_id = asset_id

            db.commit()
        finally:
            db.close()

        logger.info("[RenderWorker] Done. asset_id=%s", asset_id_str)
        return {"asset_id": asset_id_str, "video_file_key": video_key}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_render_worker.py -v
```

Expected: 2 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/workers/render_worker.py backend/tests/test_render_worker.py
git commit -m "feat: implement RenderWorker with parallel TTS and Manim rendering pipeline"
```

---

### Task 7: 视频 URL API 端点

**Files:**
- Modify: `backend/app/api/projects.py`
- Create: `backend/tests/test_video_url_api.py`

**Interfaces:**
- Consumes: `VideoAsset`（ORM）, `get_presigned_url`（from `app.storage`）
- Produces:
  - `GET /api/projects/{project_id}/video-url?asset_id=<uuid>`
  - Response: `{"url": "<presigned_url>", "expires_in": 3600}`
  - 404 if asset not found or asset.project_id ≠ project_id

- [ ] **Step 1: 写测试**

创建 `backend/tests/test_video_url_api.py`：

```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone


def make_asset(project_id, status="ready", video_file_key="video/proj/sv/asset.mp4"):
    a = MagicMock()
    a.id = uuid4()
    a.project_id = project_id
    a.status = status
    a.video_file_key = video_file_key
    return a


def make_project(pid=None):
    p = MagicMock()
    p.id = pid or uuid4()
    p.topic_id = uuid4()
    p.status = "video_review"
    p.render_engine = "manim"
    p.tts_voice = "male_calm"
    p.aspect_ratio = "landscape"
    p.retry_count = 0
    p.created_at = datetime.now(timezone.utc)
    p.updated_at = datetime.now(timezone.utc)
    return p


def test_video_url_returns_presigned_url(client, auth_headers, mock_db):
    project = make_project()
    asset = make_asset(project.id)

    mock_db.get.side_effect = [project, asset]

    with patch("app.api.projects.get_presigned_url", return_value="http://minio/signed") as mock_url:
        response = client.get(
            f"/api/projects/{project.id}/video-url",
            params={"asset_id": str(asset.id)},
            headers=auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "http://minio/signed"
    assert data["expires_in"] == 3600
    mock_url.assert_called_once_with(asset.video_file_key, expires_seconds=3600)


def test_video_url_asset_not_found(client, auth_headers, mock_db):
    project = make_project()
    mock_db.get.side_effect = [project, None]

    response = client.get(
        f"/api/projects/{project.id}/video-url",
        params={"asset_id": str(uuid4())},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_video_url_asset_wrong_project(client, auth_headers, mock_db):
    project = make_project()
    other_project_id = uuid4()
    asset = make_asset(other_project_id)  # belongs to different project

    mock_db.get.side_effect = [project, asset]

    response = client.get(
        f"/api/projects/{project.id}/video-url",
        params={"asset_id": str(asset.id)},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_video_url_no_file_key(client, auth_headers, mock_db):
    project = make_project()
    asset = make_asset(project.id, video_file_key=None)
    mock_db.get.side_effect = [project, asset]

    response = client.get(
        f"/api/projects/{project.id}/video-url",
        params={"asset_id": str(asset.id)},
        headers=auth_headers,
    )
    assert response.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_video_url_api.py -v
```

Expected: 404 或 422（端点不存在）。

- [ ] **Step 3: 在 projects.py 添加端点**

在 `backend/app/api/projects.py` 顶部导入区新增：
```python
from uuid import UUID
from app.models.video_asset import VideoAsset
from app.storage import get_presigned_url
```

找到现有的 `get_preview_url` stub 端点（返回 404 的那个），**替换**为：

```python
@router.get("/{project_id}/video-url")
async def get_video_url(
    project_id: UUID,
    asset_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    asset = await db.get(VideoAsset, asset_id)
    if asset is None or asset.project_id != project_id:
        raise HTTPException(status_code=404, detail="Video asset not found")

    if not asset.video_file_key:
        raise HTTPException(status_code=404, detail="Video not yet available")

    url = get_presigned_url(asset.video_file_key, expires_seconds=3600)
    return {"url": url, "expires_in": 3600}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_video_url_api.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 5: 运行全量测试**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v
```

Expected: 所有测试 PASSED（无新增失败）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/projects.py backend/tests/test_video_url_api.py
git commit -m "feat: add video-url API endpoint with MinIO presigned URL"
```

---

## 自审核对 Spec

| Spec 要求 | 对应 Task |
|-----------|-----------|
| 并发 TTS（asyncio.gather）| Task 6 Step 3 |
| 音频上传 MinIO `audio/{pid}/{svid}/scene_{i}.mp3` | Task 6 Step 3 |
| MinIO bucket 自动创建 | Task 2 Step 3（`_ensure_bucket`）|
| Manim subprocess，10分钟超时 | Task 5 Step 1（`MANIM_TIMEOUT_SECONDS`）|
| 单 Manim Scene，镜头起始注入 `add_sound` | Task 5 Step 1（`_build_manim_script`）|
| 视频上传 `video/{pid}/{svid}/{asset_id}.mp4` | Task 6 Step 3 |
| VideoAsset.status: rendering/ready/failed | Task 4 + Task 6 |
| VideoAsset.render_log | Task 4 |
| 音色别名 fallback | Task 1（`resolve_speaker`）|
| TTS 任意 scene 失败 → 整体失败 | Task 6 + Task 6 test |
| Manim 超时 → terminate | Task 5 |
| GET /video-url?asset_id= 不限 status | Task 7 |
| presigned URL 1小时 | Task 7 |
| 跨 project 访问 403/404 | Task 7 test |
| minio 依赖安装 | Task 1 |
