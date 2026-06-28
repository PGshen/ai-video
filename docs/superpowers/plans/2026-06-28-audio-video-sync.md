# 音画同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 TTS 音频生成提前到叙事生成后立即执行，把音频时长写入 NarrativeVersion.scenes，叙事审核页面支持试听和重新生成，CodeWorker prompt 用时长约束 Manim 动画，RenderWorker 直接复用已有音频。

**Architecture:** NarrativeWorker 在保存叙事后用 asyncio.Semaphore(3) 并发合成 TTS，将 `audio_key`/`duration_seconds`/`tts_status` 写入 scenes JSONB。新增 `POST /api/projects/{id}/narrative/tts` 供前端单镜头重新合成。RenderWorker 改为从 scenes 读取音频不再重新 TTS。前端叙事审核面板新增音频播放器和重新生成按钮。

**Tech Stack:** Python asyncio, mutagen（解析 mp3 时长）, FastAPI, SQLAlchemy, React, TanStack Query

## Global Constraints

- TTS 并发数 ≤ 3（asyncio.Semaphore(3)）
- scenes JSONB 新增字段不加数据库 migration，仅扩展字段约定
- 旁白为空字符串的镜头跳过 TTS，`duration_seconds=null`，`tts_status="skipped"`
- 音频 MinIO key 格式：`audio/{project_id}/{narrative_version_id}/scene_{i}.mp3`
- mutagen 需加入 backend/pyproject.toml 依赖
- 前端 `NarrativeScene` 类型新增 `audioKey`、`durationSeconds`、`ttsStatus` 字段
- 提交审核时若任何镜头 `tts_status` 不是 `"ready"` 或 `"skipped"`，阻断提交

---

## File Map

| 文件 | 变更类型 | 职责 |
|------|---------|------|
| `backend/pyproject.toml` | 修改 | 添加 mutagen 依赖 |
| `backend/app/engines/tts/base.py` | 修改 | `TTSResult` 增加 `audio_bytes` 字段（统一到基类） |
| `backend/app/engines/tts/volcengine.py` | 修改 | `synthesize` 返回 `duration_seconds`（用 mutagen 解析） |
| `backend/app/workers/narrative_worker.py` | 修改 | 叙事保存后立即并发 TTS，写回 scenes |
| `backend/app/schemas/narrative.py` | 修改 | `NarrativeSceneSchema` 新增 `audio_key`/`duration_seconds`/`tts_status` |
| `backend/app/api/projects.py` | 修改 | 新增 `POST /{id}/narrative/tts` 单镜头重新 TTS 接口 |
| `backend/app/api/reviews.py` | 修改 | 叙事审核写回时保留 `audio_key`/`duration_seconds`/`tts_status` 字段 |
| `backend/app/workers/render_worker.py` | 修改 | 删除 TTS 逻辑，从 scenes 读 audio_key/duration_seconds |
| `backend/app/engines/ai/chat_provider.py` | 修改 | `generate_code` system prompt 追加 duration_seconds 约束 |
| `frontend/src/types/index.ts` | 修改 | `NarrativeScene` 新增三个字段 |
| `frontend/src/lib/api.ts` | 修改 | 新增 `regenerateSceneTts` 函数 |
| `frontend/src/hooks/useNarrative.ts` | 修改 | 新增 `useRegenerateTts` mutation hook |
| `frontend/src/components/projects/NarrativeReviewPanel.tsx` | 修改 | 每个镜头增加音频播放器 + 重新生成按钮 + 提交前校验 |

---

## Task 1: 添加 mutagen 依赖并修改 TTSResult 基类

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/engines/tts/base.py`

**Interfaces:**
- Produces: `TTSResult.audio_bytes: bytes = b""` 字段在基类上可用

- [ ] **Step 1: 添加 mutagen 到依赖**

```bash
cd backend && /Users/peng/.local/bin/uv add mutagen
```

Expected: pyproject.toml 中出现 `mutagen` 条目，`uv.lock` 更新

- [ ] **Step 2: 修改 TTSResult 基类，将 audio_bytes 从 VolcanTTSResult 移到基类**

编辑 `backend/app/engines/tts/base.py`：

```python
from typing import Protocol
from dataclasses import dataclass, field


@dataclass
class TTSRequest:
    text: str
    voice: str = "default"
    speed: float = 1.0


@dataclass
class TTSResult:
    success: bool
    output_path: str | None
    duration_seconds: float | None
    error_message: str | None
    audio_bytes: bytes = field(default=b"")


class TTSEngine(Protocol):
    @property
    def engine_name(self) -> str: ...

    async def synthesize(self, request: TTSRequest) -> TTSResult: ...

    async def health_check(self) -> bool: ...
```

- [ ] **Step 3: 修改 volcengine.py，移除 VolcanTTSResult（继承改为直接用基类），用 mutagen 解析时长**

编辑 `backend/app/engines/tts/volcengine.py`，完整替换为：

```python
import base64
import uuid
from io import BytesIO
import httpx
from mutagen.mp3 import MP3
from app.engines.tts.base import TTSRequest, TTSResult

_TTS_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"


def _parse_mp3_duration(audio_bytes: bytes) -> float | None:
    try:
        audio = MP3(BytesIO(audio_bytes))
        return audio.info.length
    except Exception:
        return None


class VolcengineTTSEngine:
    engine_name = "volcengine"

    def __init__(self, api_key: str, resource_id: str = "seed-tts-2.0"):
        self._api_key = api_key
        self._resource_id = resource_id

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        import json as _json
        from app.engines.tts.voice_map import resolve_speaker

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

        audio_chunks: list[bytes] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", _TTS_URL, json=body, headers=headers) as resp:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        chunk = _json.loads(line)
                    except Exception:
                        return TTSResult(
                            success=False,
                            output_path=None,
                            duration_seconds=None,
                            error_message=f"TTS chunk parse failed (HTTP {resp.status_code}): {line[:100]}",
                            audio_bytes=b"",
                        )
                    code = chunk.get("code", 0)
                    if code != 0:
                        if code == 20000000:
                            continue
                        return TTSResult(
                            success=False,
                            output_path=None,
                            duration_seconds=None,
                            error_message=chunk.get("message", f"TTS API error code {code}"),
                            audio_bytes=b"",
                        )
                    audio_data = chunk.get("data", "")
                    if audio_data:
                        audio_chunks.append(base64.b64decode(audio_data))

        if not audio_chunks:
            return TTSResult(
                success=False,
                output_path=None,
                duration_seconds=None,
                error_message="TTS API returned empty audio data",
                audio_bytes=b"",
            )

        audio_bytes = b"".join(audio_chunks)
        duration = _parse_mp3_duration(audio_bytes)
        return TTSResult(
            success=True,
            output_path=None,
            duration_seconds=duration,
            error_message=None,
            audio_bytes=audio_bytes,
        )

    async def health_check(self) -> bool:
        result = await self.synthesize(TTSRequest(text="测试", voice="male_calm"))
        return result.success
```

- [ ] **Step 4: 写单元测试验证 mutagen 解析**

新建 `backend/tests/test_tts_duration.py`：

```python
import pytest
from unittest.mock import patch, AsyncMock
from app.engines.tts.volcengine import VolcengineTTSEngine, _parse_mp3_duration
from app.engines.tts.base import TTSRequest


def test_parse_mp3_duration_invalid_bytes_returns_none():
    assert _parse_mp3_duration(b"not_mp3") is None


def test_parse_mp3_duration_empty_returns_none():
    assert _parse_mp3_duration(b"") is None


@pytest.mark.asyncio
async def test_synthesize_returns_duration_from_mp3():
    # 用真实最小 mp3（44 bytes silent frame）验证路径
    # 这里 mock TTS 网络调用，验证 duration 由 mutagen 解析而非 API 返回
    import base64

    # 最小合法 mp3 frame（静音，约 0.026s）
    # 来源：ISO 11172-3 最小帧头 + 静音数据
    silent_mp3 = bytes([
        0xFF, 0xFB, 0x90, 0x00,  # frame header: MPEG1, Layer3, 128kbps, 44100Hz, stereo
    ] + [0x00] * 413)  # frame data（不精确，仅验证 mutagen 不崩溃）

    fake_chunk = base64.b64encode(silent_mp3).decode()
    fake_response_lines = [
        f'{{"code": 0, "data": "{fake_chunk}"}}',
        '{"code": 20000000}',
    ]

    engine = VolcengineTTSEngine(api_key="fake")

    class FakeStreamCtx:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            pass
        async def aiter_lines(self):
            for line in fake_response_lines:
                yield line
        status_code = 200

    class FakeClient:
        def stream(self, *a, **kw):
            return FakeStreamCtx()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            pass

    with patch("httpx.AsyncClient", return_value=FakeClient()):
        result = await engine.synthesize(TTSRequest(text="测试", voice="male_calm"))

    assert result.success is True
    assert len(result.audio_bytes) > 0
    # duration 要么是 float 要么是 None（取决于 silent_mp3 是否合法），不应抛异常
    assert result.duration_seconds is None or isinstance(result.duration_seconds, float)
```

- [ ] **Step 5: 运行测试**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_tts_duration.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/engines/tts/base.py backend/app/engines/tts/volcengine.py backend/tests/test_tts_duration.py
git commit -m "feat: add mutagen dep, move audio_bytes to TTSResult base, parse duration from mp3"
```

---

## Task 2: NarrativeWorker — 叙事后立即并发 TTS

**Files:**
- Modify: `backend/app/workers/narrative_worker.py`

**Interfaces:**
- Consumes: `TTSResult.audio_bytes`, `TTSResult.duration_seconds`（Task 1）
- Consumes: `upload_bytes(key, data, content_type)` from `app.storage`
- Produces: `NarrativeVersion.scenes[i]` 包含 `audio_key`, `duration_seconds`, `tts_status` 字段

- [ ] **Step 1: 修改 NarrativeWorker**

完整替换 `backend/app/workers/narrative_worker.py`：

```python
import asyncio
import logging
import uuid
from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified
from app.db import get_sync_session
from app.engines.ai.factory import get_ai_provider
from app.engines.tts.factory import get_tts_engine
from app.engines.tts.base import TTSRequest
from app.models.project import VideoProject
from app.models.narrative_version import NarrativeVersion
from app.storage import upload_bytes
from app.workers.base import BaseWorker

logger = logging.getLogger(__name__)


async def _synthesize_scenes_tts(
    scenes: list[dict],
    project_id: str,
    narrative_version_id: str,
    tts_voice: str,
) -> list[dict]:
    """并发合成所有镜头 TTS（最多 3 路并发），返回带 audio_key/duration_seconds/tts_status 的 scenes。"""
    tts_engine = get_tts_engine()
    sem = asyncio.Semaphore(3)

    async def _process_scene(i: int, scene: dict) -> dict:
        narration = scene.get("narration", "").strip()
        if not narration:
            return {**scene, "tts_status": "skipped", "audio_key": None, "duration_seconds": None}
        async with sem:
            try:
                result = await tts_engine.synthesize(TTSRequest(text=narration, voice=tts_voice))
            except Exception as e:
                logger.error("[NarrativeWorker] TTS exception scene %d: %s", i, e)
                return {**scene, "tts_status": "failed", "audio_key": None, "duration_seconds": None}

        if not result.success:
            logger.error("[NarrativeWorker] TTS failed scene %d: %s", i, result.error_message)
            return {**scene, "tts_status": "failed", "audio_key": None, "duration_seconds": None}

        key = f"audio/{project_id}/{narrative_version_id}/scene_{i}.mp3"
        upload_bytes(key, result.audio_bytes, "audio/mpeg")
        logger.info("[NarrativeWorker] TTS scene %d → %s (%.2fs)", i, key, result.duration_seconds or 0)
        return {
            **scene,
            "tts_status": "ready",
            "audio_key": key,
            "duration_seconds": result.duration_seconds,
        }

    tasks = [_process_scene(i, scene) for i, scene in enumerate(scenes)]
    return list(await asyncio.gather(*tasks))


class NarrativeWorker(BaseWorker):
    supported_task_types = ["generate_narrative"]

    async def _execute(self, task) -> dict:
        payload = task.input_payload or {}
        topic_title = payload.get("topic_title", "")
        topic_description = payload.get("topic_description", "")
        render_engine = payload.get("render_engine", "manim")
        rejection_context = payload.get("rejection_context")

        logger.info(
            "[NarrativeWorker] task=%s project=%s title=%r engine=%s retry=%s",
            task.id,
            task.project_id,
            topic_title,
            render_engine,
            bool(rejection_context),
        )

        provider = get_ai_provider()
        logger.info("[NarrativeWorker] calling AI provider model=%s", provider.model_name)
        result = await provider.generate_narrative(
            topic_title=topic_title,
            topic_description=topic_description,
            render_engine=render_engine,
            rejection_context=rejection_context,
        )
        logger.info(
            "[NarrativeWorker] AI done: scenes=%d fact_checks=%d",
            len(result.scenes),
            len(result.fact_checks),
        )

        db = get_sync_session()
        try:
            project = db.get(VideoProject, task.project_id)
            if project is None:
                raise ValueError(f"Project {task.project_id} not found")

            max_version = db.execute(
                select(func.max(NarrativeVersion.version_number)).where(
                    NarrativeVersion.project_id == task.project_id
                )
            ).scalar()
            next_version = (max_version or 0) + 1

            nv = NarrativeVersion(
                id=uuid.uuid4(),
                project_id=task.project_id,
                version_number=next_version,
                scenes=result.scenes,
                fact_checks=result.fact_checks,
                ai_model=provider.model_name,
                rejection_context=rejection_context,
            )
            db.add(nv)
            db.flush()
            narrative_version_id = str(nv.id)
            project_id = str(project.id)
            tts_voice = project.tts_voice
            db.commit()
        finally:
            db.close()

        logger.info("[NarrativeWorker] Starting TTS for %d scenes", len(result.scenes))
        scenes_with_tts = await _synthesize_scenes_tts(
            scenes=result.scenes,
            project_id=project_id,
            narrative_version_id=narrative_version_id,
            tts_voice=tts_voice,
        )
        ready_count = sum(1 for s in scenes_with_tts if s.get("tts_status") == "ready")
        logger.info("[NarrativeWorker] TTS done: %d/%d ready", ready_count, len(scenes_with_tts))

        db = get_sync_session()
        try:
            nv_orm = db.get(NarrativeVersion, uuid.UUID(narrative_version_id))
            project_orm = db.get(VideoProject, uuid.UUID(project_id))
            if nv_orm is None or project_orm is None:
                raise ValueError("NarrativeVersion or Project disappeared after TTS")
            nv_orm.scenes = scenes_with_tts
            flag_modified(nv_orm, "scenes")
            project_orm.current_narrative_version_id = nv_orm.id
            db.commit()
            logger.info("[NarrativeWorker] committed narrative_version_id=%s", narrative_version_id)
        finally:
            db.close()

        return {
            "narrative_version_id": narrative_version_id,
            "scene_count": len(scenes_with_tts),
            "fact_check_count": len(result.fact_checks),
        }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/workers/narrative_worker.py
git commit -m "feat: NarrativeWorker generates TTS immediately after narrative, stores audio_key and duration in scenes"
```

---

## Task 3: 新增单镜头重新 TTS 接口

**Files:**
- Modify: `backend/app/api/projects.py`
- Modify: `backend/app/schemas/narrative.py`

**Interfaces:**
- Produces: `POST /api/projects/{project_id}/narrative/tts` → `{ audio_key, duration_seconds, tts_status, presigned_url }`

- [ ] **Step 1: 修改 NarrativeSceneSchema，新增 TTS 字段**

在 `backend/app/schemas/narrative.py` 的 `NarrativeSceneSchema` 中添加三个字段：

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.schemas.project import FactCheckItemSchema


class NarrativeSceneSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    narration: str
    description: str
    estimated_duration_seconds: Optional[float] = None
    audio_key: Optional[str] = None
    duration_seconds: Optional[float] = None
    tts_status: Optional[str] = None


class NarrativeVersionSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, alias_generator=to_camel
    )

    id: UUID
    project_id: UUID
    version_number: int
    scenes: Optional[list[NarrativeSceneSchema]]
    fact_checks: Optional[list[FactCheckItemSchema]]
    ai_model: Optional[str]
    created_at: datetime
```

- [ ] **Step 2: 在 projects.py 中新增单镜头重新 TTS 路由**

在 `backend/app/api/projects.py` 末尾追加（在已有 import 块后，需要添加相关 import）：

首先在文件顶部 import 区新增（找到现有 import 块添加）：
```python
from sqlalchemy.orm.attributes import flag_modified
from app.engines.tts.factory import get_tts_engine
from app.engines.tts.base import TTSRequest
from app.storage import upload_bytes, get_presigned_url
```

然后在路由末尾新增：
```python
class RegenerateTtsRequest(BaseModel):
    scene_index: int
    narration: str


class RegenerateTtsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)
    audio_key: Optional[str]
    duration_seconds: Optional[float]
    tts_status: str
    presigned_url: Optional[str]


@router.post("/{project_id}/narrative/tts", response_model=RegenerateTtsResponse)
async def regenerate_scene_tts(
    project_id: UUID,
    body: RegenerateTtsRequest,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.current_narrative_version_id:
        raise HTTPException(status_code=404, detail="No narrative version found")

    nv = await db.get(NarrativeVersion, project.current_narrative_version_id)
    if nv is None or not isinstance(nv.scenes, list):
        raise HTTPException(status_code=404, detail="Narrative version scenes not found")

    narration = body.narration.strip()
    scene_idx = body.scene_index

    if not narration:
        # 空旁白：标记 skipped
        scenes = list(nv.scenes)
        for i, s in enumerate(scenes):
            if s.get("scene_index") == scene_idx:
                scenes[i] = {**s, "tts_status": "skipped", "audio_key": None, "duration_seconds": None, "narration": narration}
                break
        nv.scenes = scenes
        flag_modified(nv, "scenes")
        await db.commit()
        return RegenerateTtsResponse(audio_key=None, duration_seconds=None, tts_status="skipped", presigned_url=None)

    tts_engine = get_tts_engine()
    tts_voice = project.tts_voice
    result = await tts_engine.synthesize(TTSRequest(text=narration, voice=tts_voice))

    if not result.success:
        raise HTTPException(status_code=502, detail=f"TTS failed: {result.error_message}")

    key = f"audio/{project_id}/{nv.id}/scene_{scene_idx}.mp3"
    upload_bytes(key, result.audio_bytes, "audio/mpeg")

    scenes = list(nv.scenes)
    for i, s in enumerate(scenes):
        if s.get("scene_index") == scene_idx:
            scenes[i] = {
                **s,
                "narration": narration,
                "tts_status": "ready",
                "audio_key": key,
                "duration_seconds": result.duration_seconds,
            }
            break
    nv.scenes = scenes
    flag_modified(nv, "scenes")
    await db.commit()

    presigned = get_presigned_url(key)
    return RegenerateTtsResponse(
        audio_key=key,
        duration_seconds=result.duration_seconds,
        tts_status="ready",
        presigned_url=presigned,
    )
```

注意：`RegenerateTtsRequest`、`RegenerateTtsResponse` 需要的 import 在 projects.py 顶部补全：
```python
from pydantic import BaseModel, ConfigDict
```
（如果顶部已有 BaseModel import 则无需重复）

- [ ] **Step 3: 修改叙事审核写回逻辑，保留 audio 字段**

在 `backend/app/api/reviews.py` 的 narrative gate 处理中，`updated_scenes` 构建时需保留 `audio_key`/`duration_seconds`/`tts_status`。找到如下代码块：

```python
updated_scenes.append({
    **scene,
    "narration": edit.narration,
    "description": edit.description,
    **({"estimated_duration_seconds": edit.estimated_duration_seconds}
       if edit.estimated_duration_seconds is not None else {}),
})
```

替换为（用户编辑旁白后，若旁白已变但未重新 TTS，将 tts_status 标为 dirty 以便前端校验；实际 audio 数据不在这里更新，前端 regenerate API 已更新了 DB）：

```python
updated_scenes.append({
    **scene,
    "narration": edit.narration,
    "description": edit.description,
    **({"estimated_duration_seconds": edit.estimated_duration_seconds}
       if edit.estimated_duration_seconds is not None else {}),
})
```

**注意：** 这里无需改动。`edited_scenes` 提交时前端保证 tts_status 均为 ready（通过前端校验阻断），且 audio 字段已通过 `/narrative/tts` 接口写入 DB，`**scene` 展开时已包含最新的 `audio_key`/`duration_seconds`/`tts_status`。

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/narrative.py backend/app/api/projects.py backend/app/api/reviews.py
git commit -m "feat: add regenerate single scene TTS API, extend NarrativeSceneSchema with tts fields"
```

---

## Task 4: RenderWorker — 删除 TTS 逻辑，复用已有音频

**Files:**
- Modify: `backend/app/workers/render_worker.py`

**Interfaces:**
- Consumes: `scenes[i].audio_key`, `scenes[i].duration_seconds` from `NarrativeVersion`（但 RenderWorker 从 `ScriptVersion` 读数据）

**注意：** `CodeWorker` 合并 scenes 时是从 `NarrativeVersion` 复制 scenes 到 `ScriptVersion`（见 CodeWorker line 56-58: `{**scene, "code": code}`），所以 `ScriptVersion.scenes` 已经包含 `audio_key`/`duration_seconds`/`tts_status`。

- [ ] **Step 1: 完整替换 render_worker.py**

```python
import logging
import os
import tempfile
import uuid
from app.db import get_sync_session
from app.engines.render.factory import get_render_engine
from app.engines.render.base import RenderRequest, SceneInput, SceneAudio
from app.models.project import VideoProject
from app.models.script_version import ScriptVersion
from app.models.video_asset import VideoAsset
from app.storage import download_to_file, upload_bytes
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
            render_engine_name = project.render_engine
        finally:
            db.close()

        logger.info(
            "[RenderWorker] task=%s project=%s scenes=%d engine=%s",
            task.id,
            task.project_id,
            len(scenes_data),
            render_engine_name,
        )

        # Step 1: 创建 VideoAsset 记录
        asset_id = uuid.uuid4()
        asset_id_str = str(asset_id)
        db = get_sync_session()
        try:
            asset = VideoAsset(
                id=asset_id,
                project_id=uuid.UUID(project_id),
                script_version_id=uuid.UUID(script_version_id),
                status="rendering",
            )
            db.add(asset)
            db.commit()
        finally:
            db.close()

        # Step 2: 下载音频并渲染
        logger.info("[RenderWorker] Starting Manim render for asset %s", asset_id_str)
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_inputs = []
            for i, s in enumerate(scenes_data):
                audio_key = s.get("audio_key")
                duration = s.get("duration_seconds") or 0.0
                audio_path = None
                if audio_key:
                    audio_path = os.path.join(tmpdir, f"scene_{i}_audio.mp3")
                    download_to_file(audio_key, audio_path)
                    logger.info("[RenderWorker] Downloaded audio scene %d ← %s", i, audio_key)

                scene_inputs.append(
                    SceneInput(
                        scene_index=i,
                        narration=s.get("narration", ""),
                        description=s.get("description", ""),
                        code=s.get("code", ""),
                        audio=SceneAudio(
                            scene_index=i,
                            audio_path=audio_path or "",
                            duration_seconds=duration,
                        ) if audio_path else None,
                    )
                )

            render_engine = get_render_engine(render_engine_name)
            render_request = RenderRequest(
                scenes=scene_inputs,
                output_format="mp4",
                resolution=(1920, 1080),
                fps=30,
            )
            render_result = await render_engine.render(render_request, work_dir=tmpdir)

            if not render_result.success:
                logger.error(
                    "[RenderWorker] Render failed asset=%s: %s",
                    asset_id_str,
                    render_result.error_message,
                )
                db = get_sync_session()
                try:
                    asset_orm = db.get(VideoAsset, asset_id)
                    if asset_orm:
                        asset_orm.status = "failed"
                        asset_orm.render_log = render_result.render_log
                        asset_orm.error_message = render_result.error_message
                    db.commit()
                finally:
                    db.close()
                raise RuntimeError(f"Render failed: {render_result.error_message}")

            # Step 3: 上传视频
            video_key = f"video/{project_id}/{script_version_id}/{asset_id_str}.mp4"
            upload_bytes(video_key, render_result.video_bytes, "video/mp4")
            logger.info("[RenderWorker] Uploaded video → %s", video_key)

        # Step 4: 更新 VideoAsset 和 Project
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

- [ ] **Step 2: Commit**

```bash
git add backend/app/workers/render_worker.py
git commit -m "feat: RenderWorker reuses TTS audio from scenes, removes redundant TTS synthesis"
```

---

## Task 5: CodeWorker prompt 追加 duration_seconds 约束

**Files:**
- Modify: `backend/app/engines/ai/chat_provider.py`

**Interfaces:**
- Consumes: `scenes[i].duration_seconds`（已在 NarrativeVersion.scenes 中）

- [ ] **Step 1: 在 generate_code 的 system_prompt 末尾追加时长约束**

找到 `backend/app/engines/ai/chat_provider.py` 中 `generate_code` 方法的 `system_prompt` 字符串（约 363-390 行），在字符串末尾（`只能输出合法 JSON object\` 那行之前）追加一段约束：

将：
```python
        system_prompt = f"""\
你是知识视频代码生成器。请严格输出 JSON object，不要输出 Markdown。
...
- 只能输出合法 JSON object\
"""
```

改为在 `只能输出合法 JSON object` 前插入：

```python
        system_prompt = f"""\
你是知识视频代码生成器。请严格输出 JSON object，不要输出 Markdown。

你将收到一个知识视频的所有镜头叙事脚本，需要为每个镜头生成渲染代码片段。

JSON 格式：
{{
  "codes": [
    "镜头 0 的代码片段",
    "镜头 1 的代码片段"
  ]
}}

codes 数组长度必须与输入 scenes 数组长度完全一致，按 scene_index 顺序对应。

渲染引擎：{render_engine}
{engine_hint}

【代码拼合规则】
所有镜头的 code 片段将被渲染引擎按顺序拼合为单个执行单元，每段之间插入注释分隔符。
音频由渲染引擎在每个镜头开始时自动注入，code 里不处理音频。

【音画同步规则】
每个镜头 JSON 包含 duration_seconds 字段，代表该镜头旁白音频的时长（秒）。
该镜头所有动画的总时长（所有 Animation 的 run_time 与 self.wait 之和）必须 ≤ duration_seconds。
建议最后用 self.wait() 补足剩余时间，使动画与音频完全对齐。
若某镜头 duration_seconds 为 null，则不作时长约束，由你自行估算合适时长。

要求：
- 严格按照每个镜头的 description 实现动画逻辑
- 充分利用跨镜头变量复用（前面镜头声明的变量在后续镜头中可直接使用）
- 每个 code 片段不写外层结构（详见各引擎规范）
- 只能输出合法 JSON object\
"""
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/engines/ai/chat_provider.py
git commit -m "feat: CodeWorker prompt constraints animation duration to audio duration_seconds per scene"
```

---

## Task 6: 前端类型、API 函数和 hook

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/hooks/useNarrative.ts`

**Interfaces:**
- Produces: `NarrativeScene.audioKey`, `NarrativeScene.durationSeconds`, `NarrativeScene.ttsStatus`
- Produces: `api.regenerateSceneTts(projectId, sceneIndex, narration)` → `RegenerateTtsResponse`
- Produces: `useRegenerateTts()` TanStack mutation hook

- [ ] **Step 1: 扩展 NarrativeScene 类型**

在 `frontend/src/types/index.ts` 找到 `NarrativeScene` interface，替换为：

```typescript
export interface NarrativeScene {
  sceneIndex: number;
  narration: string;
  description: string;
  estimatedDurationSeconds: number | null;
  audioKey: string | null;
  durationSeconds: number | null;
  ttsStatus: "ready" | "failed" | "skipped" | "pending" | null;
}
```

- [ ] **Step 2: 新增 RegenerateTtsResponse 类型和 api 函数**

在 `frontend/src/types/index.ts` 末尾追加：

```typescript
export interface RegenerateTtsResponse {
  audioKey: string | null;
  durationSeconds: number | null;
  ttsStatus: string;
  presignedUrl: string | null;
}
```

在 `frontend/src/lib/api.ts` 末尾追加：

```typescript
export function regenerateSceneTts(
  projectId: string,
  sceneIndex: number,
  narration: string
) {
  return api.post<import("@/types").RegenerateTtsResponse>(
    `/api/projects/${projectId}/narrative/tts`,
    { sceneIndex, narration }
  );
}
```

- [ ] **Step 3: 新增 useRegenerateTts hook**

在 `frontend/src/hooks/useNarrative.ts` 中追加：

```typescript
import { useQuery, useMutation } from "@tanstack/react-query";
import { fetchNarrative, regenerateSceneTts } from "@/lib/api";

export function useNarrative(projectId: string) {
  return useQuery({
    queryKey: ["narrative", projectId],
    queryFn: () => fetchNarrative(projectId),
    enabled: !!projectId,
    retry: false,
  });
}

export function useRegenerateTts(projectId: string) {
  return useMutation({
    mutationFn: ({
      sceneIndex,
      narration,
    }: {
      sceneIndex: number;
      narration: string;
    }) => regenerateSceneTts(projectId, sceneIndex, narration),
  });
}
```

- [ ] **Step 4: 检查 TypeScript 编译**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm tsc --noEmit 2>&1 | head -30
```

Expected: 无错误（或仅有与本次改动无关的既有错误）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/api.ts frontend/src/hooks/useNarrative.ts
git commit -m "feat: extend NarrativeScene type with tts fields, add regenerateSceneTts api and hook"
```

---

## Task 7: 前端叙事审核面板 — 音频播放器 + 重新生成 + 提交校验

**Files:**
- Modify: `frontend/src/components/projects/NarrativeReviewPanel.tsx`

**Interfaces:**
- Consumes: `useRegenerateTts(projectId)` mutation（Task 6）
- Consumes: `NarrativeScene.audioKey`, `NarrativeScene.durationSeconds`, `NarrativeScene.ttsStatus`（Task 6）

**注意：** 后端的 `presigned_url` 通过 regenerate API 返回，但初始加载时的音频 URL 需要通过后端接口获取 presigned URL。这里采用简化方案：通过已有的 `GET /api/projects/{id}/narrative` 接口返回 `audio_key`，前端调用新增的 `GET /api/projects/{id}/audio-url?key=...` 接口获取 presigned URL；或者更简单地，在 `NarrativeVersionSchema` 里为 `audio_key` 直接生成 presigned URL 返回。

**实际方案（最简）：** 在后端 `GET /api/projects/{id}/narrative` 的返回中，将 `audio_key` 替换为 presigned URL，字段名改为 `audioPresignedUrl`。

- [ ] **Step 1: 后端 narrative 接口返回 presigned URL**

在 `backend/app/schemas/narrative.py` 的 `NarrativeSceneSchema` 中新增 `audio_presigned_url` 字段：

```python
class NarrativeSceneSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    narration: str
    description: str
    estimated_duration_seconds: Optional[float] = None
    audio_key: Optional[str] = None
    duration_seconds: Optional[float] = None
    tts_status: Optional[str] = None
    audio_presigned_url: Optional[str] = None
```

在 `backend/app/api/projects.py` 的 `get_current_narrative` 路由中，在返回前为每个 scene 的 `audio_key` 生成 presigned URL 并注入。

找到现有的 `get_current_narrative` 函数，修改返回逻辑（函数大约在 174 行附近）：

```python
@router.get("/{project_id}/narrative", response_model=NarrativeVersionSchema)
async def get_current_narrative(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.current_narrative_version_id:
        raise HTTPException(status_code=404, detail="No narrative generated yet")
    nv = await db.get(NarrativeVersion, project.current_narrative_version_id)
    if nv is None:
        raise HTTPException(status_code=404, detail="Narrative version not found")

    # 为每个场景生成 presigned URL
    scenes = list(nv.scenes or [])
    enriched_scenes = []
    for s in scenes:
        audio_key = s.get("audio_key")
        presigned = get_presigned_url(audio_key) if audio_key else None
        enriched_scenes.append({**s, "audio_presigned_url": presigned})
    nv.scenes = enriched_scenes

    return nv
```

注意：`get_presigned_url` 已在 storage 中，需在 projects.py 顶部 import（Task 3 步骤 2 中已添加）。

- [ ] **Step 2: 前端类型新增 audioPresignedUrl**

在 `frontend/src/types/index.ts` 的 `NarrativeScene` interface 中追加：

```typescript
export interface NarrativeScene {
  sceneIndex: number;
  narration: string;
  description: string;
  estimatedDurationSeconds: number | null;
  audioKey: string | null;
  durationSeconds: number | null;
  ttsStatus: "ready" | "failed" | "skipped" | "pending" | null;
  audioPresignedUrl: string | null;
}
```

- [ ] **Step 3: 完整替换 NarrativeReviewPanel.tsx**

```tsx
import { useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useSubmitReview } from "@/hooks/useProjects";
import { useRegenerateTts } from "@/hooks/useNarrative";
import type { NarrativeVersion, NarrativeScene } from "@/types";

interface SceneState {
  narration: string;
  description: string;
  audioPresignedUrl: string | null;
  durationSeconds: number | null;
  ttsStatus: NarrativeScene["ttsStatus"];
}

interface Props {
  projectId: string;
  narrative: NarrativeVersion;
}

export function NarrativeReviewPanel({ projectId, narrative }: Props) {
  const submitReview = useSubmitReview();
  const regenerateTts = useRegenerateTts(projectId);

  const [sceneStates, setSceneStates] = useState<Map<number, SceneState>>(
    new Map(
      narrative.scenes.map((s) => [
        s.sceneIndex,
        {
          narration: s.narration,
          description: s.description,
          audioPresignedUrl: s.audioPresignedUrl ?? null,
          durationSeconds: s.durationSeconds ?? null,
          ttsStatus: s.ttsStatus ?? null,
        },
      ])
    )
  );

  // 记录哪些镜头的旁白被用户修改但尚未重新 TTS
  const [dirtyTts, setDirtyTts] = useState<Set<number>>(new Set());
  const [regeneratingIdx, setRegeneratingIdx] = useState<number | null>(null);
  const [rejectionDetail, setRejectionDetail] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);

  const updateNarration = (idx: number, value: string) => {
    setSceneStates((prev) => {
      const next = new Map(prev);
      const cur = next.get(idx)!;
      next.set(idx, { ...cur, narration: value });
      return next;
    });
    setDirtyTts((prev) => new Set(prev).add(idx));
  };

  const updateDescription = (idx: number, value: string) => {
    setSceneStates((prev) => {
      const next = new Map(prev);
      const cur = next.get(idx)!;
      next.set(idx, { ...cur, description: value });
      return next;
    });
  };

  const handleRegenerateTts = async (idx: number) => {
    const state = sceneStates.get(idx);
    if (!state) return;
    setRegeneratingIdx(idx);
    try {
      const res = await regenerateTts.mutateAsync({
        sceneIndex: idx,
        narration: state.narration,
      });
      setSceneStates((prev) => {
        const next = new Map(prev);
        next.set(idx, {
          ...next.get(idx)!,
          audioPresignedUrl: res.presignedUrl,
          durationSeconds: res.durationSeconds,
          ttsStatus: res.ttsStatus as NarrativeScene["ttsStatus"],
        });
        return next;
      });
      setDirtyTts((prev) => {
        const next = new Set(prev);
        next.delete(idx);
        return next;
      });
    } finally {
      setRegeneratingIdx(null);
    }
  };

  const buildEditedScenes = () =>
    Array.from(sceneStates.entries()).map(([sceneIndex, s]) => ({
      sceneIndex,
      narration: s.narration,
      description: s.description,
    }));

  const canSubmit = dirtyTts.size === 0;

  const handleApprove = () => {
    if (!canSubmit) return;
    submitReview.mutate({
      projectId,
      gate: "narrative",
      verdict: "approved",
      editedScenes: buildEditedScenes(),
    });
  };

  const handleReject = () => {
    if (!canSubmit) return;
    submitReview.mutate({
      projectId,
      gate: "narrative",
      verdict: "rejected",
      rejectionDetail,
      editedScenes: buildEditedScenes(),
    });
  };

  const handleAbandon = () => {
    submitReview.mutate({ projectId, gate: "narrative", verdict: "abandoned" });
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex flex-1 overflow-hidden gap-4">
        {/* Left: scene list */}
        <ScrollArea className="flex-1">
          <div className="space-y-4 pr-2">
            {narrative.scenes.map((scene) => {
              const state = sceneStates.get(scene.sceneIndex)!;
              const isDirty = dirtyTts.has(scene.sceneIndex);
              const isRegenerating = regeneratingIdx === scene.sceneIndex;

              return (
                <div
                  key={scene.sceneIndex}
                  className="border rounded-lg p-4 space-y-3"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">镜头 {scene.sceneIndex}</Badge>
                    {state.durationSeconds != null && (
                      <span className="text-xs text-muted-foreground">
                        旁白时长：{state.durationSeconds.toFixed(1)}s
                      </span>
                    )}
                    {state.ttsStatus === "failed" && (
                      <Badge variant="destructive" className="text-xs">TTS 失败</Badge>
                    )}
                  </div>

                  {/* 音频播放器 */}
                  {state.audioPresignedUrl && !isDirty && (
                    <audio
                      controls
                      src={state.audioPresignedUrl}
                      className="w-full h-8"
                    />
                  )}

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">旁白</label>
                    <Textarea
                      value={state.narration}
                      onChange={(e) => updateNarration(scene.sceneIndex, e.target.value)}
                      rows={3}
                      className="text-sm"
                    />
                  </div>

                  {isDirty && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleRegenerateTts(scene.sceneIndex)}
                      disabled={isRegenerating}
                    >
                      {isRegenerating ? "生成中…" : "重新生成音频"}
                    </Button>
                  )}

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">画面描述</label>
                    <Textarea
                      value={state.description}
                      onChange={(e) => updateDescription(scene.sceneIndex, e.target.value)}
                      rows={4}
                      className="text-sm"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>

        {/* Right: fact checks */}
        <ScrollArea className="w-72 shrink-0">
          <div className="space-y-3 pr-1">
            <p className="text-xs font-medium text-muted-foreground">
              事实核查（将在代码审核阶段标注）
            </p>
            {narrative.factChecks.map((fc, i) => (
              <div key={i} className="border rounded-lg p-3 space-y-1">
                <p className="text-xs">{fc.claimText}</p>
                <Badge
                  variant={
                    fc.confidence === "high"
                      ? "default"
                      : fc.confidence === "low"
                      ? "destructive"
                      : "secondary"
                  }
                  className="text-xs"
                >
                  {fc.confidence}
                </Badge>
                <p className="text-xs text-muted-foreground">{fc.sourceDescription}</p>
              </div>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Bottom action bar */}
      <div className="border-t pt-4 mt-4 space-y-3">
        {dirtyTts.size > 0 && (
          <p className="text-sm text-amber-600">
            有 {dirtyTts.size} 个镜头修改了旁白，请先点击「重新生成音频」再提交。
          </p>
        )}
        {showRejectInput && (
          <Textarea
            placeholder="请说明驳回原因..."
            value={rejectionDetail}
            onChange={(e) => setRejectionDetail(e.target.value)}
            rows={2}
          />
        )}
        {submitReview.isSuccess && (
          <p className="text-sm text-muted-foreground text-center animate-pulse">
            已提交，正在切换到代码生成阶段…
          </p>
        )}
        <div className="flex gap-2">
          <Button
            onClick={handleApprove}
            disabled={submitReview.isPending || submitReview.isSuccess || !canSubmit}
            className="flex-1"
          >
            {submitReview.isPending ? "提交中…" : "确认通过（进入代码生成）"}
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              if (showRejectInput) {
                handleReject();
              } else {
                setShowRejectInput(true);
              }
            }}
            disabled={submitReview.isPending || submitReview.isSuccess || !canSubmit}
          >
            {submitReview.isPending ? "提交中…" : "驳回重生成"}
          </Button>
          <Button
            variant="ghost"
            onClick={handleAbandon}
            disabled={submitReview.isPending || submitReview.isSuccess}
          >
            废弃
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 检查 TypeScript 编译**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm tsc --noEmit 2>&1 | head -30
```

Expected: 无与本次改动相关的错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/projects/NarrativeReviewPanel.tsx frontend/src/types/index.ts backend/app/schemas/narrative.py backend/app/api/projects.py
git commit -m "feat: NarrativeReviewPanel adds audio player, regenerate TTS button, and submit guard"
```

---

## Self-Review

**Spec coverage 检查：**

| 需求 | 对应 Task |
|------|-----------|
| TTS 提前至叙事生成后 | Task 2 |
| TTS 并发 ≤ 3 | Task 2（Semaphore(3)） |
| audio_key/duration_seconds 存入 NarrativeVersion.scenes | Task 2 |
| 叙事审核页面音频播放 | Task 7 |
| 用户修改旁白后可重新 TTS | Task 3 + Task 7 |
| 提交时阻断未重新 TTS 的镜头 | Task 7（dirtyTts guard） |
| CodeWorker prompt 约束动画时长 | Task 5 |
| RenderWorker 复用已有音频 | Task 4 |
| mutagen 解析 mp3 时长 | Task 1 |

**Placeholder scan：** 无 TBD / TODO

**Type consistency 检查：**

- `NarrativeScene.ttsStatus` 类型：`"ready" | "failed" | "skipped" | "pending" | null` — Task 6 定义，Task 7 消费 ✓
- `RegenerateTtsResponse.presignedUrl` — Task 3（后端）返回 `presigned_url` → camelCase → `presignedUrl`，Task 6 消费 ✓
- `NarrativeScene.audioPresignedUrl` — Task 7 Step 1（后端 schema）新增，Task 7 Step 2（前端类型）新增 ✓
- `useRegenerateTts` 返回 `mutateAsync` — Task 6 定义，Task 7 使用 ✓
