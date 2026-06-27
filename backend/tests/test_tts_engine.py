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
