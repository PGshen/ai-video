import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_active_user
from app.db import get_async_session
from app.config import settings
from app.engines.tts.base import TTSRequest
from app.engines.tts.factory import build_tts_engine
from app.models.project import VideoProject
from app.models.tts_config import TTSEngineConfig, TTSVoice
from app.schemas.tts_config import (
    TTSEngineCreate,
    TTSEngineResponse,
    TTSEngineUpdate,
    TTSSettingsResponse,
    TTSVoiceCreate,
    TTSVoiceResponse,
    TTSVoicePreviewRequest,
    TTSVoiceUpdate,
)

router = APIRouter(prefix="/api/tts-settings", tags=["tts-settings"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _engine_response(engine: TTSEngineConfig) -> TTSEngineResponse:
    return TTSEngineResponse(
        id=engine.id,
        name=engine.name,
        code=engine.code,
        provider_type=engine.provider_type,
        endpoint=engine.endpoint,
        resource_id=engine.resource_id,
        timeout_seconds=engine.timeout_seconds,
        is_active=engine.is_active,
        api_key_set=bool(engine.api_key),
        created_at=engine.created_at,
        updated_at=engine.updated_at,
    )


def _voice_response(voice: TTSVoice) -> TTSVoiceResponse:
    return TTSVoiceResponse.model_validate(voice, from_attributes=True)


async def _ensure_unique_engine_code(
    db: AsyncSession, code: str, excluding_id: uuid.UUID | None = None
) -> None:
    stmt = select(TTSEngineConfig.id).where(TTSEngineConfig.code == code)
    if excluding_id:
        stmt = stmt.where(TTSEngineConfig.id != excluding_id)
    if (await db.execute(stmt.limit(1))).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="引擎编码已存在")


async def _ensure_unique_voice_name(
    db: AsyncSession, engine_id: uuid.UUID, name: str, excluding_id: uuid.UUID | None = None
) -> None:
    stmt = select(TTSVoice.id).where(TTSVoice.engine_id == engine_id, TTSVoice.name == name)
    if excluding_id:
        stmt = stmt.where(TTSVoice.id != excluding_id)
    if (await db.execute(stmt.limit(1))).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="该引擎下音色名称已存在")


@router.get("", response_model=TTSSettingsResponse)
async def get_tts_settings(
    active_only: bool = False,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    engine_stmt = select(TTSEngineConfig).order_by(TTSEngineConfig.created_at.asc())
    voice_stmt = select(TTSVoice).order_by(TTSVoice.created_at.asc())
    if active_only:
        engine_stmt = engine_stmt.where(TTSEngineConfig.is_active.is_(True))
        voice_stmt = voice_stmt.where(TTSVoice.is_active.is_(True))
    engines = (await db.execute(engine_stmt)).scalars().all()
    engine_ids = {engine.id for engine in engines}
    voices = (await db.execute(voice_stmt)).scalars().all()
    return TTSSettingsResponse(
        engines=[_engine_response(engine) for engine in engines],
        voices=[_voice_response(voice) for voice in voices if voice.engine_id in engine_ids],
    )


@router.post("/engines", response_model=TTSEngineResponse, status_code=201)
async def create_engine(
    body: TTSEngineCreate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    await _ensure_unique_engine_code(db, body.code)
    engine = TTSEngineConfig(id=uuid.uuid4(), **body.model_dump())
    db.add(engine)
    await db.commit()
    await db.refresh(engine)
    return _engine_response(engine)


@router.put("/engines/{engine_id}", response_model=TTSEngineResponse)
async def update_engine(
    engine_id: uuid.UUID,
    body: TTSEngineUpdate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    engine = await db.get(TTSEngineConfig, engine_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="TTS 引擎不存在")
    data = body.model_dump(exclude_unset=True)
    if data.get("code"):
        await _ensure_unique_engine_code(db, data["code"], engine_id)
    old_code = engine.code
    for field, value in data.items():
        if field == "api_key" and not value:
            continue
        setattr(engine, field, value)
    if engine.code != old_code:
        await db.execute(
            update(VideoProject)
            .where(VideoProject.tts_engine == old_code)
            .values(tts_engine=engine.code)
        )
    engine.updated_at = _now()
    await db.commit()
    await db.refresh(engine)
    return _engine_response(engine)


@router.delete("/engines/{engine_id}", status_code=204)
async def delete_engine(
    engine_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    engine = await db.get(TTSEngineConfig, engine_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="TTS 引擎不存在")
    if (await db.execute(select(TTSVoice.id).where(TTSVoice.engine_id == engine_id).limit(1))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="请先删除该引擎下的音色")
    if (await db.execute(select(VideoProject.id).where(VideoProject.tts_engine == engine.code).limit(1))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该引擎已被视频项目使用，可停用但不能删除")
    await db.delete(engine)
    await db.commit()


@router.post("/voices", response_model=TTSVoiceResponse, status_code=201)
async def create_voice(
    body: TTSVoiceCreate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    if await db.get(TTSEngineConfig, body.engine_id) is None:
        raise HTTPException(status_code=404, detail="TTS 引擎不存在")
    await _ensure_unique_voice_name(db, body.engine_id, body.name)
    voice = TTSVoice(id=uuid.uuid4(), **body.model_dump())
    db.add(voice)
    await db.commit()
    await db.refresh(voice)
    return _voice_response(voice)


@router.put("/voices/{voice_id}", response_model=TTSVoiceResponse)
async def update_voice(
    voice_id: uuid.UUID,
    body: TTSVoiceUpdate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    voice = await db.get(TTSVoice, voice_id)
    if voice is None:
        raise HTTPException(status_code=404, detail="TTS 音色不存在")
    data = body.model_dump(exclude_unset=True)
    old_engine = await db.get(TTSEngineConfig, voice.engine_id)
    old_engine_code = old_engine.code if old_engine else None
    old_voice_name = voice.name
    engine_id = data.get("engine_id", voice.engine_id)
    if await db.get(TTSEngineConfig, engine_id) is None:
        raise HTTPException(status_code=404, detail="TTS 引擎不存在")
    await _ensure_unique_voice_name(db, engine_id, data.get("name", voice.name), voice_id)
    for field, value in data.items():
        setattr(voice, field, value)
    new_engine = await db.get(TTSEngineConfig, voice.engine_id)
    if old_engine_code and new_engine and (
        old_engine_code != new_engine.code or old_voice_name != voice.name
    ):
        await db.execute(
            update(VideoProject)
            .where(
                VideoProject.tts_engine == old_engine_code,
                VideoProject.tts_voice == old_voice_name,
            )
            .values(tts_engine=new_engine.code, tts_voice=voice.name)
        )
    voice.updated_at = _now()
    await db.commit()
    await db.refresh(voice)
    return _voice_response(voice)


@router.delete("/voices/{voice_id}", status_code=204)
async def delete_voice(
    voice_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    voice = await db.get(TTSVoice, voice_id)
    if voice is None:
        raise HTTPException(status_code=404, detail="TTS 音色不存在")
    engine = await db.get(TTSEngineConfig, voice.engine_id)
    if engine and (await db.execute(
        select(VideoProject.id).where(
            VideoProject.tts_engine == engine.code,
            VideoProject.tts_voice == voice.name,
        ).limit(1)
    )).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该音色已被视频项目使用，可停用但不能删除")
    await db.delete(voice)
    await db.commit()


@router.post("/voices/{voice_id}/preview")
async def preview_voice(
    voice_id: uuid.UUID,
    body: TTSVoicePreviewRequest,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    voice = await db.get(TTSVoice, voice_id)
    if voice is None:
        raise HTTPException(status_code=404, detail="TTS 音色不存在")
    engine = await db.get(TTSEngineConfig, voice.engine_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="TTS 引擎不存在")
    api_key = engine.api_key or settings.VOLCENGINE_TTS_API_KEY
    if not api_key:
        raise HTTPException(status_code=422, detail="该引擎尚未配置 API Key")
    tts_engine = build_tts_engine(
        code=engine.code,
        api_key=api_key,
        resource_id=engine.resource_id,
        endpoint=engine.endpoint,
        timeout_seconds=engine.timeout_seconds,
        voices={voice.name: voice.speaker_id},
    )
    try:
        result = await tts_engine.synthesize(
            TTSRequest(text=body.text.strip(), voice=voice.name, speed=body.speed)
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"音色试听失败：{exc}") from exc
    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=f"音色试听失败：{result.error_message or '未知错误'}",
        )
    return Response(
        content=result.audio_bytes,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )
