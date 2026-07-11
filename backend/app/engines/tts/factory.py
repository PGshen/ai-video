from app.config import settings
from app.engines.tts.volcengine import VolcengineTTSEngine


def get_tts_engine(engine: str = "doubao_2.0") -> VolcengineTTSEngine:
    resource_ids = {
        "doubao_1.0": settings.VOLCENGINE_TTS_1_RESOURCE_ID,
        "doubao_2.0": settings.VOLCENGINE_TTS_RESOURCE_ID,
    }
    resource_id = resource_ids.get(engine)
    if resource_id is None:
        raise ValueError(f"Unsupported TTS engine: {engine}")
    return VolcengineTTSEngine(
        api_key=settings.VOLCENGINE_TTS_API_KEY,
        resource_id=resource_id,
        engine=engine,
    )
