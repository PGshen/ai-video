import logging
import uuid
from sqlalchemy import func, select
from app.db import get_sync_session
from app.engines.ai.factory import get_ai_provider
from app.engines.render.base import SceneInput
from app.engines.render.factory import get_render_engine
from app.models.project import VideoProject
from app.models.narrative_version import NarrativeVersion
from app.models.script_version import ScriptVersion
from app.workers.base import BaseWorker
from app.services.narrative_validator import validate_scenes_for_codegen

_MAX_VALIDATION_ROUNDS = 2

logger = logging.getLogger(__name__)


class CodeWorker(BaseWorker):
    supported_task_types = ["generate_code"]

    async def _execute(self, task) -> dict:
        payload = task.input_payload or {}
        render_engine = payload.get("render_engine", "manim")
        style_components: dict[str, str] = payload.get("style_components") or {}
        prompt_snapshot: dict = payload.get("prompt_snapshot") or {}
        if not prompt_snapshot:
            raise ValueError("generate_code task requires prompt_snapshot")

        logger.info(
            "[CodeWorker] task=%s project=%s engine=%s",
            task.id,
            task.project_id,
            render_engine,
        )

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
            validate_scenes_for_codegen(scenes)
            logger.info(
                "[CodeWorker] loaded narrative_version=%s scenes=%d",
                project.current_narrative_version_id,
                len(scenes),
            )

            provider = get_ai_provider()
            logger.info("[CodeWorker] calling AI provider model=%s", provider.model_name)
            codegen_scenes = [
                {
                    "scene_index": scene["scene_index"],
                    "narration": scene["narration"],
                    "description": scene["description"],
                    "duration_seconds": scene.get("duration_seconds"),
                    "beats": scene["beats"],
                }
                for scene in scenes
            ]
            result = await provider.generate_code(
                scenes=codegen_scenes,
                render_engine=render_engine,
                style_components=style_components,
            )
            logger.info("[CodeWorker] AI done: codes=%d", len(result.codes))

            # Merge code into scenes (match by position / scene_index order)
            merged_scenes = []
            for i, scene in enumerate(scenes):
                code = result.codes[i] if i < len(result.codes) else ""
                merged_scenes.append({**scene, "code": code})

            # Validate and auto-repair (manim only; other engines skip gracefully)
            render_engine_obj = get_render_engine(render_engine)
            for round_num in range(_MAX_VALIDATION_ROUNDS):
                scene_inputs = [
                    SceneInput(
                        scene_index=i,
                        narration=s.get("narration", ""),
                        description=s.get("description", ""),
                        code=s.get("code", ""),
                        audio=None,
                    )
                    for i, s in enumerate(merged_scenes)
                ]
                is_valid, errors = await render_engine_obj.validate_code(scene_inputs)
                if is_valid:
                    logger.info("[CodeWorker] validation passed (round %d)", round_num)
                    break
                logger.info(
                    "[CodeWorker] validation round %d/%d failed, repairing...",
                    round_num + 1,
                    _MAX_VALIDATION_ROUNDS,
                )
                repair_result = await provider.repair_code(
                    scenes=merged_scenes,
                    render_engine=render_engine,
                    error_message=errors,
                )
                for r in repair_result.repairs:
                    idx = r["scene_index"]
                    merged_scenes[idx] = {**merged_scenes[idx], "code": r["code"]}
                    logger.info(
                        "[CodeWorker] repaired scene %d: %s",
                        idx,
                        r.get("explanation", "")[:120],
                    )
            else:
                # Final validation after last repair
                scene_inputs = [
                    SceneInput(
                        scene_index=i,
                        narration=s.get("narration", ""),
                        description=s.get("description", ""),
                        code=s.get("code", ""),
                        audio=None,
                    )
                    for i, s in enumerate(merged_scenes)
                ]
                is_valid, errors = await render_engine_obj.validate_code(scene_inputs)
                if is_valid:
                    logger.info("[CodeWorker] validation passed after final repair")
                else:
                    logger.warning(
                        "[CodeWorker] validation still failing after %d rounds, saving anyway:\n%s",
                        _MAX_VALIDATION_ROUNDS,
                        errors[:500],
                    )

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
                prompt_snapshot=prompt_snapshot,
            )
            db.add(sv)
            db.flush()

            project.current_script_version_id = sv.id
            db.commit()
            logger.info(
                "[CodeWorker] committed script_version_id=%s version=%d",
                sv.id,
                next_version,
            )

            return {
                "script_version_id": str(sv.id),
                "scene_count": len(merged_scenes),
                "fact_check_count": len(fact_checks),
            }
        finally:
            db.close()
