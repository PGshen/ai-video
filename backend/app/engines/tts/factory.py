from app.config import settings
from app.engines.tts.volcengine import VolcengineTTSEngine
from app.db import get_sync_session
from app.models.tts_config import TTSEngineConfig, TTSVoice
from sqlalchemy import select


def build_tts_engine(
    *,
    code: str,
    api_key: str,
    resource_id: str,
    endpoint: str,
    timeout_seconds: float,
    voices: dict[str, str],
) -> VolcengineTTSEngine:
    return VolcengineTTSEngine(
        api_key=api_key,
        resource_id=resource_id,
        engine=code,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        voices=voices,
    )


def get_tts_engine(engine: str) -> VolcengineTTSEngine:
    """Load an active engine and its active voices for synchronous workers."""
    db = get_sync_session()
    try:
        config = db.execute(
            select(TTSEngineConfig).where(
                TTSEngineConfig.code == engine,
                TTSEngineConfig.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if config is None:
            raise ValueError(f"TTS engine {engine!r} is missing or inactive")
        voices = db.execute(
            select(TTSVoice).where(
                TTSVoice.engine_id == config.id,
                TTSVoice.is_active.is_(True),
            )
        ).scalars().all()
        api_key = config.api_key or settings.VOLCENGINE_TTS_API_KEY
        return build_tts_engine(
            code=config.code,
            api_key=api_key,
            resource_id=config.resource_id,
            endpoint=config.endpoint,
            timeout_seconds=config.timeout_seconds,
            voices={voice.name: voice.speaker_id for voice in voices},
        )
    finally:
        db.close()
