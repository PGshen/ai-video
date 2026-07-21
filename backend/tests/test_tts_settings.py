from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.tts_settings import get_tts_settings, preview_voice
from app.engines.tts.base import TTSResult
from app.schemas.tts_config import TTSVoicePreviewRequest


@pytest.mark.asyncio
async def test_get_tts_settings_returns_engines_with_nested_voices_and_masks_key(mock_db):
    now = datetime.now(timezone.utc)
    engine_id = uuid4()
    engine = SimpleNamespace(
        id=engine_id,
        name="自定义豆包",
        code="custom_doubao",
        provider_type="volcengine",
        endpoint="https://tts.example.test/synthesize",
        api_key="secret",
        resource_id="seed-tts-2.0",
        timeout_seconds=30.0,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    voice = SimpleNamespace(
        id=uuid4(),
        engine_id=engine_id,
        name="讲解员",
        speaker_id="provider-speaker-id",
        language="zh-CN",
        gender="female",
        description="知识讲解",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    engine_result = MagicMock()
    engine_result.scalars.return_value.all.return_value = [engine]
    voice_result = MagicMock()
    voice_result.scalars.return_value.all.return_value = [voice]
    mock_db.execute.side_effect = [engine_result, voice_result]

    response = await get_tts_settings(active_only=False, db=mock_db, _=object())
    data = response.model_dump(by_alias=True, mode="json")
    assert data["engines"][0]["code"] == "custom_doubao"
    assert data["engines"][0]["apiKeySet"] is True
    assert "apiKey" not in data["engines"][0]
    assert data["voices"][0]["engineId"] == str(engine_id)
    assert data["voices"][0]["speakerId"] == "provider-speaker-id"


@pytest.mark.asyncio
async def test_preview_voice_returns_generated_mp3(mock_db):
    engine_id = uuid4()
    voice = SimpleNamespace(
        id=uuid4(),
        engine_id=engine_id,
        name="讲解员",
        speaker_id="provider-speaker-id",
    )
    engine = SimpleNamespace(
        id=engine_id,
        code="custom_doubao",
        api_key="secret",
        resource_id="seed-tts-2.0",
        endpoint="https://tts.example.test/synthesize",
        timeout_seconds=30.0,
    )
    mock_db.get.side_effect = [voice, engine]
    tts_engine = MagicMock()
    tts_engine.synthesize = AsyncMock(
        return_value=TTSResult(
            success=True,
            output_path=None,
            duration_seconds=1.2,
            error_message=None,
            audio_bytes=b"test-mp3",
        )
    )

    with patch("app.api.tts_settings.build_tts_engine", return_value=tts_engine):
        response = await preview_voice(
            voice_id=voice.id,
            body=TTSVoicePreviewRequest(text="试听文字"),
            db=mock_db,
            _=object(),
        )

    assert response.media_type == "audio/mpeg"
    assert response.body == b"test-mp3"
    request = tts_engine.synthesize.await_args.args[0]
    assert request.voice == "讲解员"
    assert request.text == "试听文字"
