import uuid
from sqlalchemy import func, select
from app.db import get_sync_session
from app.engines.ai.factory import get_ai_provider
from app.models.project import VideoProject
from app.models.narrative_version import NarrativeVersion
from app.models.script_version import ScriptVersion
from app.workers.base import BaseWorker


class CodeWorker(BaseWorker):
    supported_task_types = ["generate_code"]

    async def _execute(self, task) -> dict:
        payload = task.input_payload or {}
        render_engine = payload.get("render_engine", "manim")

        db = get_sync_session()
        try:
            project = db.get(VideoProject, task.project_id)
            if project is None:
                raise ValueError(f"Project {task.project_id} not found")

            narrative = db.get(NarrativeVersion, project.current_narrative_version_id)
            if narrative is None:
                raise ValueError("No narrative version found for project")

            scenes = list(narrative.scenes or [])
            fact_checks = list(narrative.fact_checks or [])

            provider = get_ai_provider()
            result = await provider.generate_code(
                scenes=scenes,
                render_engine=render_engine,
            )

            # Merge code into scenes (match by position / scene_index order)
            merged_scenes = []
            for i, scene in enumerate(scenes):
                code = result.codes[i] if i < len(result.codes) else ""
                merged_scenes.append({**scene, "code": code})

            max_version = db.execute(
                select(func.max(ScriptVersion.version_number)).where(
                    ScriptVersion.project_id == task.project_id
                )
            ).scalar()
            next_version = (max_version or 0) + 1

            sv = ScriptVersion(
                id=uuid.uuid4(),
                project_id=task.project_id,
                version_number=next_version,
                scenes=merged_scenes,
                fact_checks=fact_checks,
                render_engine=render_engine,
                ai_model=provider.model_name,
            )
            db.add(sv)
            db.flush()

            project.current_script_version_id = sv.id
            db.commit()

            return {
                "script_version_id": str(sv.id),
                "scene_count": len(merged_scenes),
                "fact_check_count": len(fact_checks),
            }
        finally:
            db.close()
