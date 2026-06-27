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
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(_TTS_URL, json=body, headers=headers)

        data = resp.json()
        if data.get("code", 0) != 0:
            return VolcanTTSResult(
                success=False,
                output_path=None,
                duration_seconds=None,
                error_message=data.get("message", "TTS API error"),
                audio_bytes=b"",
            )

        audio_bytes = base64.b64decode(data["data"])
        return VolcanTTSResult(
            success=True,
            output_path=None,
            duration_seconds=None,
            error_message=None,
            audio_bytes=audio_bytes,
        )

    async def health_check(self) -> bool:
        result = await self.synthesize(TTSRequest(text="测试", voice="male_calm"))
        return result.success
