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
        import json as _json

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

        # 接口返回 chunked 流式响应，每个 chunk 是独立的 JSON 行，需逐行解析累积音频
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
                        return VolcanTTSResult(
                            success=False,
                            output_path=None,
                            duration_seconds=None,
                            error_message=f"TTS chunk parse failed (HTTP {resp.status_code}): {line[:100]}",
                            audio_bytes=b"",
                        )
                    code = chunk.get("code", 0)
                    if code != 0:
                        # 20000000 是流式传输正常结束标志，跳过
                        if code == 20000000:
                            continue
                        return VolcanTTSResult(
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
            return VolcanTTSResult(
                success=False,
                output_path=None,
                duration_seconds=None,
                error_message="TTS API returned empty audio data",
                audio_bytes=b"",
            )

        return VolcanTTSResult(
            success=True,
            output_path=None,
            duration_seconds=None,
            error_message=None,
            audio_bytes=b"".join(audio_chunks),
        )

    async def health_check(self) -> bool:
        result = await self.synthesize(TTSRequest(text="测试", voice="male_calm"))
        return result.success
