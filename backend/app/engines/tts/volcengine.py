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
