import uuid
from sqlalchemy import func, select
from app.db import get_sync_session
from app.engines.ai.factory import get_ai_provider
from app.models.project import VideoProject
from app.models.narrative_version import NarrativeVersion
from app.workers.base import BaseWorker


class NarrativeWorker(BaseWorker):
    supported_task_types = ["generate_narrative"]

    async def _execute(self, task) -> dict:
        payload = task.input_payload or {}
        topic_title = payload.get("topic_title", "")
        topic_description = payload.get("topic_description", "")
        render_engine = payload.get("render_engine", "manim")
        rejection_context = payload.get("rejection_context")

        provider = get_ai_provider()
        result = await provider.generate_narrative(
            topic_title=topic_title,
            topic_description=topic_description,
            render_engine=render_engine,
            rejection_context=rejection_context,
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
            )
            db.add(nv)
            db.flush()

            project.current_narrative_version_id = nv.id
            db.commit()

            return {
                "narrative_version_id": str(nv.id),
                "scene_count": len(result.scenes),
                "fact_check_count": len(result.fact_checks),
            }
        finally:
            db.close()
