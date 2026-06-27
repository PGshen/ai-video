from app.config import settings
from app.engines.tts.volcengine import VolcengineTTSEngine


def get_tts_engine() -> VolcengineTTSEngine:
    return VolcengineTTSEngine(
        api_key=settings.VOLCENGINE_TTS_API_KEY,
        resource_id=settings.VOLCENGINE_TTS_RESOURCE_ID,
    )
