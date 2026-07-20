import logging
import re
import uuid
from sqlalchemy import func, select
from app.db import get_sync_session
from app.engines.ai.factory import get_ai_provider
from app.engines.render.base import SceneInput
from app.engines.render.factory import get_render_engine
from app.models.project import VideoProject
from app.models.narrative_version import NarrativeVersion
from app.models.code_version import CodeVersion
from app.workers.base import BaseWorker
from app.services.narrative_validator import validate_scenes_for_codegen

_MAX_VALIDATION_ROUNDS = 2
_ERROR_SCENE_RE = re.compile(r"scene (\d+):")

logger = logging.getLogger(__name__)


def _error_scene_indices(errors: str) -> set[int] | None:
    """Extract scene indices the render engine attributed errors to.

    Returns None when *no* error line carries a "scene N:" attribution
    (e.g. a timeout or an error outside any scene method) — the caller
    should fall back to sending every scene as repair context, since we
    can't safely narrow it down.
    """
    matches = _ERROR_SCENE_RE.findall(errors)
    return {int(m) for m in matches} if matches else None


class CodeWorker(BaseWorker):
    supported_task_types = ["generate_code"]

    async def _execute(self, task) -> dict:
        payload = task.input_payload or {}
        render_engine = payload.get("render_engine", "manim")
        aspect_ratio = payload.get("aspect_ratio")
        style_components: dict[str, str] = payload.get("style_components") or {}
        prompt_snapshot: dict = payload.get("prompt_snapshot") or {}
        rejection_context = payload.get("rejection_context")
        previous_code_scenes = payload.get("previous_code_scenes")
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
            aspect_ratio = aspect_ratio or project.aspect_ratio or "landscape"

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

            provider = get_ai_provider("code_generation")
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
                aspect_ratio=aspect_ratio,
                rejection_context=rejection_context,
                previous_code_scenes=previous_code_scenes,
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
                error_scenes = _error_scene_indices(errors)
                if error_scenes is not None:
                    # Errors are attributed to specific scenes: a scene can
                    # only be a root cause of something that runs *after* it,
                    # so it's safe (and much cheaper) to hand the repair model
                    # just the erroring scene(s) and everything before them,
                    # rather than every scene in the project.
                    context_upto = max(error_scenes)
                    repair_scenes = [
                        s for s in merged_scenes if s.get("scene_index", 0) <= context_upto
                    ]
                    context_truncated = len(repair_scenes) < len(merged_scenes)
                    logger.info(
                        "[CodeWorker] scoped repair to scenes 0..%d (%d/%d scenes) — attributed: %s",
                        context_upto,
                        len(repair_scenes),
                        len(merged_scenes),
                        sorted(error_scenes),
                    )
                else:
                    # Errors we can't attribute to a scene (timeout, error
                    # outside any _scene_N method, engines without scene
                    # attribution) — degrade to the old behavior of sending
                    # every scene so the model has full context.
                    repair_scenes = merged_scenes
                    context_truncated = False
                    logger.info("[CodeWorker] could not attribute errors to scenes, repairing with full context")

                repair_provider = get_ai_provider("code_repair")
                repair_result = await repair_provider.repair_code(
                    scenes=repair_scenes,
                    render_engine=render_engine,
                    error_message=errors,
                    style_components=style_components,
                    aspect_ratio=aspect_ratio,
                    context_truncated=context_truncated,
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
                        "[CodeWorker] validation still failing after %d rounds:\n%s",
                        _MAX_VALIDATION_ROUNDS,
                        errors[:500],
                    )
                    raise ValueError(
                        f"Code validation failed after {_MAX_VALIDATION_ROUNDS} repair rounds:\n{errors[:2000]}"
                    )

            max_version = db.execute(
                select(func.max(CodeVersion.version_number)).where(
                    CodeVersion.project_id == task.project_id
                )
            ).scalar()
            next_version = (max_version or 0) + 1

            code_version = CodeVersion(
                id=uuid.uuid4(),
                project_id=task.project_id,
                version_number=next_version,
                scenes=merged_scenes,
                fact_checks=fact_checks,
                render_engine=render_engine,
                ai_model=provider.model_name,
                rejection_context=rejection_context,
                prompt_snapshot=prompt_snapshot,
            )
            db.add(code_version)
            db.flush()

            project.current_code_version_id = code_version.id
            db.commit()
            logger.info(
                "[CodeWorker] committed code_version_id=%s version=%d",
                code_version.id,
                next_version,
            )

            return {
                "code_version_id": str(code_version.id),
                "scene_count": len(merged_scenes),
                "fact_check_count": len(fact_checks),
            }
        finally:
            db.close()
