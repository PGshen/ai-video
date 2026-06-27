import logging
import uuid
from sqlalchemy import func, select
from app.db import get_sync_session
from app.engines.ai.factory import get_ai_provider
from app.models.project import VideoProject
from app.models.narrative_version import NarrativeVersion
from app.workers.base import BaseWorker

logger = logging.getLogger(__name__)


class NarrativeWorker(BaseWorker):
    supported_task_types = ["generate_narrative"]

    async def _execute(self, task) -> dict:
        payload = task.input_payload or {}
        topic_title = payload.get("topic_title", "")
        topic_description = payload.get("topic_description", "")
        render_engine = payload.get("render_engine", "manim")
        rejection_context = payload.get("rejection_context")

        logger.info(
            "[NarrativeWorker] task=%s project=%s title=%r engine=%s retry=%s",
            task.id,
            task.project_id,
            topic_title,
            render_engine,
            bool(rejection_context),
        )
        if rejection_context:
            logger.info("[NarrativeWorker] rejection_context: %s", rejection_context)

        provider = get_ai_provider()
        logger.info("[NarrativeWorker] calling AI provider model=%s", provider.model_name)
        result = await provider.generate_narrative(
            topic_title=topic_title,
            topic_description=topic_description,
            render_engine=render_engine,
            rejection_context=rejection_context,
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
            logger.info("[NarrativeWorker] saving narrative version=%d for project=%s", next_version, task.project_id)

            nv = NarrativeVersion(
                id=uuid.uuid4(),
                project_id=task.project_id,
                version_number=next_version,
                scenes=result.scenes,
                fact_checks=result.fact_checks,
                ai_model=provider.model_name,
                rejection_context=rejection_context,
            )
            db.add(nv)
            db.flush()

            project.current_narrative_version_id = nv.id
            db.commit()
            logger.info("[NarrativeWorker] committed narrative_version_id=%s", nv.id)

            return {
                "narrative_version_id": str(nv.id),
                "scene_count": len(result.scenes),
                "fact_check_count": len(result.fact_checks),
            }
        finally:
            db.close()
