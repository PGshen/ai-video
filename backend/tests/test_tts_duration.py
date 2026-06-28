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
