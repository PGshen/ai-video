import base64
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from app.engines.tts.base import TTSRequest, TTSResult
from app.engines.tts.volcengine import VolcengineTTSEngine


@pytest.fixture
def engine():
    return VolcengineTTSEngine(
        api_key="test-key",
        resource_id="seed-tts-2.0",
        retry_base_delay_seconds=0,
    )


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


def _make_stream_sequence_mock(responses):
    """Build a client mock whose stream response changes for each attempt."""
    call_count = 0

    @asynccontextmanager
    async def _stream(*args, **kwargs):
        nonlocal call_count
        response = responses[call_count]
        call_count += 1
        if isinstance(response, Exception):
            raise response

        lines, status_code = response

        async def _aiter_lines():
            for line in lines:
                yield line

        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.aiter_lines = _aiter_lines
        yield mock_resp

    mock_client = MagicMock()
    mock_client.stream = _stream

    @asynccontextmanager
    async def _async_client(*args, **kwargs):
        yield mock_client

    def _call_count():
        return call_count

    return _async_client, _call_count


@pytest.mark.asyncio
async def test_synthesize_success(engine):
    audio_bytes = b"fake-audio-data"
    chunk = {"code": 0, "message": "", "data": base64.b64encode(audio_bytes).decode()}
    terminal = {"code": 20000000, "message": "OK", "data": ""}

    import json
    lines = [json.dumps(chunk), json.dumps(terminal)]

    with patch("httpx.AsyncClient", _make_stream_mock(lines)):
        result = await engine.synthesize(TTSRequest(text="你好世界", voice="zizi"))

    assert result.success is True
    assert isinstance(result, TTSResult)
    assert result.audio_bytes == audio_bytes


@pytest.mark.asyncio
async def test_synthesize_collects_and_deduplicates_word_timestamps(engine):
    import json

    audio_bytes = b"fake-audio-data"
    sentence = {
        "text": "你好，",
        "words": [
            {
                "word": "你",
                "startTime": 0.1,
                "endTime": 0.2,
                "confidence": 0.9,
            },
            {
                "word": "好，",
                "startTime": 0.2,
                "endTime": 0.5,
                "confidence": 0.8,
            },
        ],
    }
    chunk = {
        "code": 0,
        "data": base64.b64encode(audio_bytes).decode(),
        "sentence": sentence,
    }
    lines = [json.dumps(chunk), json.dumps({**chunk, "data": ""})]

    with patch("httpx.AsyncClient", _make_stream_mock(lines)):
        result = await engine.synthesize(TTSRequest(text="你好，", voice="zizi"))

    assert [(item.word, item.start_time, item.end_time) for item in result.word_timestamps] == [
        ("你", 0.1, 0.2),
        ("好，", 0.2, 0.5),
    ]


@pytest.mark.asyncio
async def test_synthesize_api_error(engine):
    import json
    error_chunk = {"code": 10001, "message": "invalid api key", "data": ""}
    lines = [json.dumps(error_chunk)]

    with patch("httpx.AsyncClient", _make_stream_mock(lines)):
        result = await engine.synthesize(TTSRequest(text="hello", voice="zizi"))

    assert result.success is False
    assert "invalid api key" in result.error_message


@pytest.mark.asyncio
async def test_synthesize_retries_transient_api_error(engine):
    import json

    audio_bytes = b"audio-after-retry"
    transient_error = {"code": 50000, "message": "service unavailable", "data": ""}
    success = {
        "code": 0,
        "message": "",
        "data": base64.b64encode(audio_bytes).decode(),
    }
    async_client, call_count = _make_stream_sequence_mock(
        [
            ([json.dumps(transient_error)], 200),
            ([json.dumps(success)], 200),
        ]
    )

    with patch("httpx.AsyncClient", async_client):
        result = await engine.synthesize(TTSRequest(text="hello", voice="zizi"))

    assert result.success is True
    assert result.audio_bytes == audio_bytes
    assert call_count() == 2


@pytest.mark.asyncio
async def test_synthesize_retries_network_error(engine):
    import json

    audio_bytes = b"audio-after-network-error"
    request = httpx.Request("POST", "https://example.test/tts")
    network_error = httpx.ConnectError("connection reset", request=request)
    success = {
        "code": 0,
        "message": "",
        "data": base64.b64encode(audio_bytes).decode(),
    }
    async_client, call_count = _make_stream_sequence_mock(
        [network_error, ([json.dumps(success)], 200)]
    )

    with patch("httpx.AsyncClient", async_client):
        result = await engine.synthesize(TTSRequest(text="hello", voice="zizi"))

    assert result.success is True
    assert result.audio_bytes == audio_bytes
    assert call_count() == 2


@pytest.mark.asyncio
async def test_synthesize_does_not_retry_non_retryable_http_error(engine):
    async_client, call_count = _make_stream_sequence_mock([([], 400)])

    with patch("httpx.AsyncClient", async_client):
        result = await engine.synthesize(TTSRequest(text="hello", voice="zizi"))

    assert result.success is False
    assert result.error_message == "TTS HTTP request failed (HTTP 400)"
    assert call_count() == 1


@pytest.mark.asyncio
async def test_synthesize_stops_after_max_retries_with_exponential_backoff():
    import json

    engine = VolcengineTTSEngine(
        api_key="test-key",
        max_retries=2,
        retry_base_delay_seconds=0.25,
    )
    transient_error = json.dumps(
        {"code": 50000, "message": "service unavailable", "data": ""}
    )
    async_client, call_count = _make_stream_sequence_mock(
        [
            ([transient_error], 200),
            ([transient_error], 200),
            ([transient_error], 200),
        ]
    )

    with (
        patch("httpx.AsyncClient", async_client),
        patch(
            "app.engines.tts.volcengine.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep,
    ):
        result = await engine.synthesize(TTSRequest(text="hello", voice="zizi"))

    assert result.success is False
    assert result.error_message == "service unavailable"
    assert call_count() == 3
    assert sleep.await_args_list == [call(0.25), call(0.5)]


@pytest.mark.asyncio
async def test_health_check_success(engine):
    with patch.object(engine, "synthesize", new_callable=AsyncMock) as mock_syn:
        mock_result = MagicMock()
        mock_result.success = True
        mock_syn.return_value = mock_result
        ok = await engine.health_check()
    assert ok is True


def test_voice_alias_resolved(engine):
    from app.engines.tts.voice_map import resolve_speaker

    assert resolve_speaker("zizi", "doubao_2.0") == "zh_female_qingchezizi_uranus_bigtts"
    assert resolve_speaker("sisi", "doubao_1.0") == "zh_female_shuangkuaisisi_moon_bigtts"
    with pytest.raises(ValueError, match="not available"):
        resolve_speaker("sisi", "doubao_2.0")


def test_tts_factory_builds_database_configured_engine_and_voice_map():
    from app.engines.tts.factory import build_tts_engine

    configured = build_tts_engine(
        code="custom_doubao",
        api_key="secret",
        resource_id="seed-tts-2.0",
        endpoint="https://tts.example.test/synthesize",
        timeout_seconds=12.5,
        voices={"narrator": "provider-speaker-id"},
    )

    assert configured._engine == "custom_doubao"
    assert configured._endpoint == "https://tts.example.test/synthesize"
    assert configured._timeout_seconds == 12.5
    assert configured._voices == {"narrator": "provider-speaker-id"}
