"""
集成测试：真实调用火山引擎 TTS 接口。
需要环境变量 VOLCENGINE_TTS_API_KEY 有效才能通过。
运行：
    cd backend
    /Users/peng/.local/bin/uv run pytest tests/test_tts_integration.py -v -s
"""
import pytest
from app.config import settings
from app.engines.tts.volcengine import VolcengineTTSEngine
from app.engines.tts.base import TTSRequest


pytestmark = pytest.mark.skipif(
    not settings.VOLCENGINE_TTS_API_KEY,
    reason="VOLCENGINE_TTS_API_KEY not set",
)


@pytest.fixture
def engine():
    return VolcengineTTSEngine(
        api_key=settings.VOLCENGINE_TTS_API_KEY,
        resource_id=settings.VOLCENGINE_TTS_RESOURCE_ID,
    )


@pytest.mark.asyncio
async def test_synthesize_real_request(engine):
    """验证真实 TTS 请求能成功返回音频字节。"""
    result = await engine.synthesize(TTSRequest(text="你好，这是一个测试。", voice="zizi"))

    print(f"\nsuccess={result.success}")
    print(f"error_message={result.error_message}")
    print(f"audio_bytes length={len(result.audio_bytes)}")

    assert result.success, f"TTS failed: {result.error_message}"
    assert len(result.audio_bytes) > 0, "audio_bytes should not be empty"


@pytest.mark.asyncio
async def test_synthesize_raw_response(engine):
    """打印原始响应，用于调试接口格式问题。"""
    import httpx
    import uuid

    from app.engines.tts.voice_map import resolve_speaker

    speaker = resolve_speaker("zizi")
    headers = {
        "X-Api-Key": engine._api_key,
        "X-Api-Resource-Id": engine._resource_id,
        "X-Api-Request-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }
    body = {
        "req_params": {
            "text": "你好",
            "speaker": speaker,
            "audio_params": {"format": "mp3", "sample_rate": 24000},
        }
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://openspeech.bytedance.com/api/v3/tts/unidirectional",
            json=body,
            headers=headers,
        )

    print(f"\nHTTP status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('content-type')}")
    print(f"Transfer-Encoding: {resp.headers.get('transfer-encoding')}")
    print(f"Response headers: {dict(resp.headers)}")
    print(f"Response body (first 500 bytes): {resp.content[:500]}")

    # 尝试解析
    try:
        data = resp.json()
        print(f"Parsed JSON keys: {list(data.keys())}")
        print(f"code={data.get('code')}, message={data.get('message')}")
        if "data" in data:
            print(f"data field length (base64): {len(data['data'])}")
    except Exception as e:
        print(f"JSON parse failed: {e}")
        print(f"Raw text (first 200): {resp.text[:200]}")
