import base64
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.tts.base import TTSRequest, TTSResult
from app.engines.tts.volcengine import VolcengineTTSEngine


@pytest.fixture
def engine():
    return VolcengineTTSEngine(api_key="test-key", resource_id="seed-tts-2.0")


def _make_stream_mock(lines: list[str]):
    """Build a mock for httpx client.stream() that yields the given lines."""

    async def _aiter_lines():
        for line in lines:
            yield line

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aiter_lines = _aiter_lines

    @asynccontextmanager
    async def _stream(*args, **kwargs):
        yield mock_resp

    mock_client = MagicMock()
    mock_client.stream = _stream

    @asynccontextmanager
    async def _async_client(*args, **kwargs):
        yield mock_client

    return _async_client


@pytest.mark.asyncio
async def test_synthesize_success(engine):
    audio_bytes = b"fake-audio-data"
    chunk = {"code": 0, "message": "", "data": base64.b64encode(audio_bytes).decode()}
    terminal = {"code": 20000000, "message": "OK", "data": ""}

    import json
    lines = [json.dumps(chunk), json.dumps(terminal)]

    with patch("httpx.AsyncClient", _make_stream_mock(lines)):
        result = await engine.synthesize(TTSRequest(text="你好世界", voice="alloy"))

    assert result.success is True
    assert isinstance(result, TTSResult)
    assert result.audio_bytes == audio_bytes


@pytest.mark.asyncio
async def test_synthesize_api_error(engine):
    import json
    error_chunk = {"code": 10001, "message": "invalid api key", "data": ""}
    lines = [json.dumps(error_chunk)]

    with patch("httpx.AsyncClient", _make_stream_mock(lines)):
        result = await engine.synthesize(TTSRequest(text="hello", voice="alloy"))

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
    assert len(VOICE_ALIAS_MAP) > 0
