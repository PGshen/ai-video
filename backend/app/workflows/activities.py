import uuid
from datetime import datetime, timezone
from temporalio import activity
from app.db import get_sync_session
from app.models.project import VideoProject
from app.models.project_event import ProjectEvent
from app.models.worker_task import WorkerTask


@activity.defn
async def update_project_status(project_id: str, new_status: str) -> None:
    db = get_sync_session()
    try:
        project = db.get(VideoProject, uuid.UUID(project_id))
        if project is None:
            return
        old_status = project.status
        project.status = new_status
        event = ProjectEvent(
            project_id=project.id,
            event_type="status_change",
            from_status=old_status,
            to_status=new_status,
            actor="workflow",
        )
        db.add(event)
        db.commit()
    finally:
        db.close()


@activity.defn
async def submit_script_generation_task(project_id: str) -> None:
    db = get_sync_session()
    try:
        project = db.get(VideoProject, uuid.UUID(project_id))
        if project is None:
            return
        task = WorkerTask(
            project_id=project.id,
            task_type="generate_script",
            engine=project.render_engine,
            status="pending",
            temporal_workflow_id=f"video-production-{project_id}",
            signal_name="script_generated",
            max_retries=3,
        )
        db.add(task)
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
        task = WorkerTask(
            project_id=project.id,
            task_type="render_video",
            engine=project.render_engine,
            status="pending",
            temporal_workflow_id=f"video-production-{project_id}",
            signal_name="render_completed",
            max_retries=3,
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
        return project.retry_count < 3
    finally:
        db.close()
