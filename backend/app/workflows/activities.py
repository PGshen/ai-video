import uuid
from datetime import datetime, timezone
from sqlalchemy import select, desc
from temporalio import activity
from app.db import get_sync_session
from app.models.project import VideoProject
from app.models.project_event import ProjectEvent
from app.models.narrative_version import NarrativeVersion
from app.models.code_version import CodeVersion
from app.models.topic import Topic
from app.models.worker_task import WorkerTask
from app.services.prompt_bundle import build_prompt_snapshot, style_components_from_snapshot


@activity.defn
async def update_project_status(project_id: str, new_status: str, payload: dict | None = None) -> None:
    db = get_sync_session()
    try:
        project = db.get(VideoProject, uuid.UUID(project_id))
        if project is None:
            return
        old_status = project.status
        project.status = new_status
        event_payload = dict(payload or {})
        version = None
        if new_status == "narrative_review" and project.current_narrative_version_id:
            version = db.get(NarrativeVersion, project.current_narrative_version_id)
            event_payload["content_type"] = "narrative"
        elif new_status == "code_review" and project.current_code_version_id:
            version = db.get(CodeVersion, project.current_code_version_id)
            event_payload["content_type"] = "code"
        if version is not None:
            event_payload["content_version_id"] = str(version.id)
            event_payload["content_version_number"] = version.version_number
        event = ProjectEvent(
            project_id=project.id,
            event_type="status_change",
            from_status=old_status,
            to_status=new_status,
            actor="workflow",
            payload=event_payload or None,
        )
        db.add(event)
        db.commit()
    finally:
        db.close()



@activity.defn
async def submit_video_generation_task(project_id: str) -> None:
    db = get_sync_session()
    try:
        project = db.get(VideoProject, uuid.UUID(project_id))
        if project is None:
            return
        if project.current_code_version_id is None:
            raise ValueError("Cannot render video without a current code version")
        task = WorkerTask(
            project_id=project.id,
            # Freeze the reviewed version when the task is queued.  The project
            # pointer is mutable and must not decide a queued task's input.
            code_version_id=project.current_code_version_id,
            task_type="render_video",
            engine=project.render_engine,
            status="pending",
            temporal_workflow_id=f"video-production-{project_id}",
            signal_name="render_completed",
            max_retries=0,
        )
        db.add(task)
        db.commit()
    finally:
        db.close()


@activity.defn
async def check_and_increment_retry(project_id: str, stage: str, error: str) -> bool:
    db = get_sync_session()
    try:
        project = db.get(VideoProject, uuid.UUID(project_id))
        if project is None:
            return False
        project.retry_count += 1
        db.commit()
        return project.retry_count < 2
    finally:
        db.close()


@activity.defn
async def submit_narrative_task(project_id: str) -> None:
    db = get_sync_session()
    try:
        project = db.get(VideoProject, uuid.UUID(project_id))
        if project is None:
            return
        topic = db.get(Topic, project.topic_id)

        rejection_event = db.execute(
            select(ProjectEvent)
            .where(
                ProjectEvent.project_id == project.id,
                ProjectEvent.event_type == "review_verdict",
                ProjectEvent.payload["verdict"].astext == "rejected",
            )
            .order_by(desc(ProjectEvent.created_at))
        ).scalars().first()
        rejection_context = rejection_event.payload if rejection_event else None
        previous_scenes = None
        if rejection_context and project.current_narrative_version_id:
            previous_narrative = db.get(NarrativeVersion, project.current_narrative_version_id)
            if previous_narrative is not None:
                previous_scenes = previous_narrative.scenes

        style_components, prompt_snapshot = build_prompt_snapshot(db, project)

        task = WorkerTask(
            project_id=project.id,
            task_type="generate_narrative",
            engine=project.render_engine,
            status="pending",
            input_payload={
                "topic_title": topic.title if topic else "",
                "topic_description": topic.description if topic else "",
                "render_engine": project.render_engine,
                "aspect_ratio": project.aspect_ratio,
                "rejection_context": rejection_context,
                "previous_scenes": previous_scenes,
                "narrative_context": project.narrative_context or [],
                "style_components": style_components,
                "prompt_snapshot": prompt_snapshot,
            },
            temporal_workflow_id=f"video-production-{project_id}",
            signal_name="narrative_generated",
            max_retries=0,
        )
        db.add(task)
        db.commit()
    finally:
        db.close()


@activity.defn
async def submit_code_task(project_id: str) -> None:
    db = get_sync_session()
    try:
        project = db.get(VideoProject, uuid.UUID(project_id))
        if project is None:
            return

        narrative = db.get(NarrativeVersion, project.current_narrative_version_id)
        if narrative is None or not isinstance(narrative.prompt_snapshot, dict):
            raise ValueError("Current narrative version has no prompt snapshot")
        prompt_snapshot = narrative.prompt_snapshot
        style_components = style_components_from_snapshot(prompt_snapshot)
        rejection_event = db.execute(
            select(ProjectEvent)
            .where(
                ProjectEvent.project_id == project.id,
                ProjectEvent.event_type == "review_verdict",
                ProjectEvent.payload["verdict"].astext == "rejected",
            )
            .order_by(desc(ProjectEvent.created_at))
        ).scalars().first()
        rejection_context = rejection_event.payload if rejection_event else None
        previous_code_scenes = None
        if rejection_context and project.current_code_version_id:
            previous_code_version = db.get(CodeVersion, project.current_code_version_id)
            if previous_code_version is not None:
                previous_code_scenes = previous_code_version.scenes

        task = WorkerTask(
            project_id=project.id,
            task_type="generate_code",
            engine=project.render_engine,
            status="pending",
            input_payload={
                "render_engine": project.render_engine,
                "aspect_ratio": project.aspect_ratio,
                "style_components": style_components,
                "prompt_snapshot": prompt_snapshot,
                "rejection_context": rejection_context,
                "previous_code_scenes": previous_code_scenes,
            },
            temporal_workflow_id=f"video-production-{project_id}",
            signal_name="code_generated",
            max_retries=0,
        )
        db.add(task)
        db.commit()
    finally:
        db.close()


class StageNotResettableError(ValueError):
    pass


_RESETTABLE_STAGES: dict[str, tuple[str, str | None]] = {
    "narrative_generating": ("generate_narrative", None),
    "code_generating": ("generate_code", None),
    "code_failed": ("generate_code", "code_generating"),
    "video_generating": ("render_video", None),
}


async def reset_stuck_stage(project_id: str) -> dict:
    db = get_sync_session()
    try:
        project = db.get(VideoProject, uuid.UUID(project_id))
        if project is None:
            raise LookupError(f"Project {project_id} not found")

        reset_config = _RESETTABLE_STAGES.get(project.status)
        if reset_config is None:
            raise StageNotResettableError(
                f"Project status '{project.status}' is not a resettable stage"
            )
        task_type, next_status = reset_config
        old_status = project.status

        stuck_tasks = db.execute(
            select(WorkerTask).where(
                WorkerTask.project_id == project.id,
                WorkerTask.task_type == task_type,
                WorkerTask.status.in_(["pending", "processing"]),
            )
        ).scalars().all()
        cancelled_ids = [str(t.id) for t in stuck_tasks]
        for t in stuck_tasks:
            t.status = "cancelled"

        if next_status is not None:
            project.status = next_status

        db.add(ProjectEvent(
            project_id=project.id,
            event_type="status_change" if next_status is not None else "stuck_reset",
            from_status=old_status,
            to_status=next_status or old_status,
            actor="operator",
            payload={
                "stage": task_type,
                "cancelled_task_ids": cancelled_ids,
                **({"trigger": "manual_retry"} if next_status is not None else {}),
            },
        ))
        db.commit()
    finally:
        db.close()

    if task_type == "generate_narrative":
        await submit_narrative_task(project_id)
    elif task_type == "generate_code":
        await submit_code_task(project_id)
    elif task_type == "render_video":
        await submit_video_generation_task(project_id)

    return {"stage": task_type, "cancelled_task_ids": cancelled_ids}
