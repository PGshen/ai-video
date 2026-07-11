import asyncio
import logging
import uuid
from dataclasses import asdict
from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified
from app.db import get_sync_session
from app.engines.ai.factory import get_ai_provider
from app.engines.tts.factory import get_tts_engine
from app.engines.tts.base import TTSRequest
from app.models.project import VideoProject
from app.models.narrative_version import NarrativeVersion
from app.storage import upload_bytes
from app.workers.base import BaseWorker
from app.services.beat_aligner import align_scene_beats

logger = logging.getLogger(__name__)


async def _synthesize_scenes_tts(
    scenes: list[dict],
    project_id: str,
    narrative_version_id: str,
    tts_voice: str,
    tts_engine_name: str,
    tts_speed: float,
) -> list[dict]:
    """并发合成所有镜头 TTS（最多 3 路并发），返回带 audio_key/duration_seconds/tts_status 的 scenes。"""
    tts_engine = get_tts_engine(tts_engine_name)
    sem = asyncio.Semaphore(3)

    async def _process_scene(i: int, scene: dict) -> dict:
        narration = scene.get("narration", "").strip()
        if not narration:
            return {**scene, "tts_status": "skipped", "audio_key": None, "duration_seconds": None}
        async with sem:
            try:
                result = await tts_engine.synthesize(
                    TTSRequest(text=narration, voice=tts_voice, speed=tts_speed)
                )
            except Exception as e:
                logger.error("[NarrativeWorker] TTS exception scene %d: %s", i, e)
                return {**scene, "tts_status": "failed", "audio_key": None, "duration_seconds": None}

        if not result.success:
            logger.error("[NarrativeWorker] TTS failed scene %d: %s", i, result.error_message)
            return {**scene, "tts_status": "failed", "audio_key": None, "duration_seconds": None}

        key = f"audio/{project_id}/{narrative_version_id}/scene_{i}.mp3"
        upload_bytes(key, result.audio_bytes, "audio/mpeg")
        logger.info("[NarrativeWorker] TTS scene %d → %s (%.2fs)", i, key, result.duration_seconds or 0)
        return {
            **scene,
            "tts_status": "ready",
            "audio_key": key,
            "duration_seconds": result.duration_seconds,
            "word_timestamps": [asdict(item) for item in result.word_timestamps],
        }

    tasks = [_process_scene(i, scene) for i, scene in enumerate(scenes)]
    synthesized = list(await asyncio.gather(*tasks))
    return [
        align_scene_beats(scene) if scene.get("tts_status") == "ready" else scene
        for scene in synthesized
    ]


class NarrativeWorker(BaseWorker):
    supported_task_types = ["generate_narrative"]

    async def _execute(self, task) -> dict:
        payload = task.input_payload or {}
        topic_title = payload.get("topic_title", "")
        topic_description = payload.get("topic_description", "")
        render_engine = payload.get("render_engine", "manim")
        aspect_ratio = payload.get("aspect_ratio", "landscape")
        rejection_context = payload.get("rejection_context")
        previous_scenes = payload.get("previous_scenes")
        narrative_context = payload.get("narrative_context") or []
        style_components: dict[str, str] = payload.get("style_components") or {}
        prompt_snapshot: dict = payload.get("prompt_snapshot") or {}
        if not prompt_snapshot:
            raise ValueError("generate_narrative task requires prompt_snapshot")

        logger.info(
            "[NarrativeWorker] task=%s project=%s title=%r engine=%s retry=%s",
            task.id,
            task.project_id,
            topic_title,
            render_engine,
            bool(rejection_context),
        )

        provider = get_ai_provider("narrative_generation")
        logger.info("[NarrativeWorker] calling AI provider model=%s", provider.model_name)
        result = await provider.generate_narrative(
            topic_title=topic_title,
            topic_description=topic_description,
            render_engine=render_engine,
            rejection_context=rejection_context,
            previous_scenes=previous_scenes,
            narrative_context=narrative_context,
            style_components=style_components,
            aspect_ratio=aspect_ratio,
        )
        logger.info(
            "[NarrativeWorker] AI done: scenes=%d fact_checks=%d",
            len(result.scenes),
            len(result.fact_checks),
        )

        db = get_sync_session()
        try:
            project = db.get(VideoProject, task.project_id)
            if project is None:
                raise ValueError(f"Project {task.project_id} not found")

            max_version = db.execute(
                select(func.max(NarrativeVersion.version_number)).where(
                    NarrativeVersion.project_id == task.project_id
                )
            ).scalar()
            next_version = (max_version or 0) + 1

            nv = NarrativeVersion(
                id=uuid.uuid4(),
                project_id=task.project_id,
                version_number=next_version,
                scenes=result.scenes,
                fact_checks=result.fact_checks,
                ai_model=provider.model_name,
                rejection_context=rejection_context,
                prompt_snapshot=prompt_snapshot,
            )
            db.add(nv)
            db.flush()
            narrative_version_id = str(nv.id)
            project_id = str(project.id)
            tts_voice = project.tts_voice
            tts_engine_name = project.tts_engine
            tts_speed = project.tts_speed
            db.commit()
        finally:
            db.close()

        logger.info("[NarrativeWorker] Starting TTS for %d scenes", len(result.scenes))
        scenes_with_tts = await _synthesize_scenes_tts(
            scenes=result.scenes,
            project_id=project_id,
            narrative_version_id=narrative_version_id,
            tts_voice=tts_voice,
            tts_engine_name=tts_engine_name,
            tts_speed=tts_speed,
        )
        ready_count = sum(1 for s in scenes_with_tts if s.get("tts_status") == "ready")
        logger.info("[NarrativeWorker] TTS done: %d/%d ready", ready_count, len(scenes_with_tts))

        db = get_sync_session()
        try:
            nv_orm = db.get(NarrativeVersion, uuid.UUID(narrative_version_id))
            project_orm = db.get(VideoProject, uuid.UUID(project_id))
            if nv_orm is None or project_orm is None:
                raise ValueError("NarrativeVersion or Project disappeared after TTS")
            nv_orm.scenes = scenes_with_tts
            flag_modified(nv_orm, "scenes")
            project_orm.current_narrative_version_id = nv_orm.id
            db.commit()
            logger.info("[NarrativeWorker] committed narrative_version_id=%s", narrative_version_id)
        finally:
            db.close()

        return {
            "narrative_version_id": narrative_version_id,
            "scene_count": len(scenes_with_tts),
            "fact_check_count": len(result.fact_checks),
        }
