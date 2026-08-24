import logging
import uuid
from sqlalchemy import func, select
from app.db import get_sync_session
from app.models.project import VideoProject
from app.models.narrative_version import NarrativeVersion
from app.models.code_version import CodeVersion
from app.workers.base import BaseWorker
from app.services.narrative_validator import validate_scenes_for_codegen
from app.services.strategies import get_codegen_strategy

logger = logging.getLogger(__name__)


def _with_execution_trace(
    prompt_snapshot: dict, execution_mode: str, trace: dict | None
) -> dict:
    """产物溯源：把执行模式与 Agent 执行信息并进 prompt_snapshot（只增键）。"""
    snapshot = {**prompt_snapshot, "execution_mode": execution_mode}
    if execution_mode != "agent":
        return snapshot
    trace = trace or {}
    snapshot["agent"] = {
        "sdk_version": trace.get("sdk_version"),
        "model": trace.get("model"),
        "max_turns": trace.get("max_turns"),
        "num_turns": trace.get("num_turns"),
        "tool_calls": trace.get("tool_calls") or [],
        "total_cost_usd": trace.get("total_cost_usd"),
        "resumed": bool(trace.get("resumed")),
        "validated_first_pass": bool(trace.get("validated_first_pass")),
    }
    return snapshot


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

            execution_mode = payload.get("execution_mode", "prompt")
            strategy = get_codegen_strategy(execution_mode)
            outcome = await strategy.run(
                scenes=scenes,
                render_engine=render_engine,
                style_components=style_components,
                aspect_ratio=aspect_ratio,
                rejection_context=rejection_context,
                previous_code_scenes=previous_code_scenes,
                task_id=task.id,
            )
            merged_scenes = outcome.scenes
            prompt_snapshot = _with_execution_trace(
                prompt_snapshot, execution_mode, outcome.trace
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
                ai_model=outcome.ai_model,
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
                "trace": outcome.trace,
            }
        finally:
            db.close()
