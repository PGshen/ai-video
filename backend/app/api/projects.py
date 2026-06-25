from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client as TemporalClient
from app.auth import verify_api_key
from app.db import get_async_session
from app.deps import get_temporal_client
from app.models.project import VideoProject
from app.models.topic import Topic
from app.models.project_event import ProjectEvent
from app.schemas.project import (
    ProjectCreate, ProjectResponse, ProjectListResponse,
    ProjectDetailResponse, EventListResponse,
)
from app.workflows.video_production import VideoProductionWorkflow
from app.config import settings

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_to_response(project, topic) -> ProjectResponse:
    """Build ProjectResponse from ORM project + optional topic object."""
    return ProjectResponse(
        id=project.id,
        topic_id=project.topic_id,
        topic_title=topic.title if topic else "",
        status=project.status,
        render_engine=project.render_engine,
        tts_voice=project.tts_voice,
        aspect_ratio=project.aspect_ratio,
        retry_count=project.retry_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    stmt = select(VideoProject)
    if status:
        stmt = stmt.where(VideoProject.status == status)
    stmt = stmt.order_by(VideoProject.created_at.desc())
    result = await db.execute(stmt)
    projects = result.scalars().all()

    # batch fetch topic titles
    topic_ids = list({p.topic_id for p in projects})
    topic_map: dict = {}
    if topic_ids:
        t_result = await db.execute(select(Topic).where(Topic.id.in_(topic_ids)))
        for t in t_result.scalars().all():
            topic_map[t.id] = t.title

    items = []
    for p in projects:
        r = ProjectResponse(
            id=p.id,
            topic_id=p.topic_id,
            topic_title=topic_map.get(p.topic_id, ""),
            status=p.status,
            render_engine=p.render_engine,
            tts_voice=p.tts_voice,
            aspect_ratio=p.aspect_ratio,
            retry_count=p.retry_count,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        items.append(r)

    return ProjectListResponse(items=items, total=len(items))


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_async_session),
    temporal: TemporalClient = Depends(get_temporal_client),
    _=Depends(verify_api_key),
):
    import uuid as _uuid
    project_id = _uuid.uuid4()
    workflow_id = f"video-production-{project_id}"

    orm_project = VideoProject(
        topic_id=body.topic_id,
        status="draft",
        render_engine=body.render_engine,
        tts_voice=body.tts_voice,
        aspect_ratio=body.aspect_ratio,
        temporal_workflow_id=workflow_id,
    )
    orm_project.id = project_id
    db.add(orm_project)
    await db.commit()

    await temporal.start_workflow(
        VideoProductionWorkflow.run,
        str(project_id),
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )

    topic = await db.get(Topic, orm_project.topic_id)
    return _project_to_response(orm_project, topic)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    topic = await db.get(Topic, project.topic_id)
    return _project_to_response(project, topic)


@router.get("/{project_id}/events", response_model=EventListResponse)
async def list_events(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    stmt = select(ProjectEvent).where(
        ProjectEvent.project_id == project_id
    ).order_by(ProjectEvent.created_at.asc())
    result = await db.execute(stmt)
    events = result.scalars().all()
    return EventListResponse(items=events)


@router.get("/{project_id}/script-versions")
async def list_script_versions(project_id: UUID, _=Depends(verify_api_key)):
    return {"items": [], "total": 0}


@router.get("/{project_id}/preview-url")
async def get_preview_url(project_id: UUID, _=Depends(verify_api_key)):
    raise HTTPException(status_code=404, detail="No video asset yet")


@router.post("/{project_id}/performance")
async def record_performance(project_id: UUID, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"POST /api/projects/{project_id}/performance"}
