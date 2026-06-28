from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from temporalio.client import Client as TemporalClient
from app.auth import verify_api_key
from app.db import get_async_session
from app.deps import get_temporal_client
from app.models.project import VideoProject
from app.models.script_version import ScriptVersion
from app.models.narrative_version import NarrativeVersion
from app.schemas.narrative import NarrativeVersionSchema
from app.models.topic import Topic
from app.models.project_event import ProjectEvent
from app.models.video_asset import VideoAsset
from app.storage import get_presigned_url, upload_bytes
from app.engines.tts.factory import get_tts_engine
from app.engines.tts.base import TTSRequest
from app.schemas.project import (
    ProjectCreate, ProjectResponse, ProjectListResponse,
    ProjectDetailResponse, EventListResponse, ScriptVersionSchema,
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
    topic = await db.get(Topic, body.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

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
    topic.status = "in_production"
    db.add(orm_project)
    await db.commit()

    await temporal.start_workflow(
        VideoProductionWorkflow.run,
        str(project_id),
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )

    return _project_to_response(orm_project, topic)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    topic = await db.get(Topic, project.topic_id)
    base = _project_to_response(project, topic)
    video_asset = None
    if project.current_video_asset_id:
        video_asset = await db.get(VideoAsset, project.current_video_asset_id)
    return ProjectDetailResponse(
        **base.model_dump(),
        current_script_version=None,
        current_video_asset=video_asset,
    )


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


@router.get("/{project_id}/script", response_model=ScriptVersionSchema)
async def get_current_script(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.current_script_version_id:
        raise HTTPException(status_code=404, detail="No script generated yet")
    sv = await db.get(ScriptVersion, project.current_script_version_id)
    if sv is None:
        raise HTTPException(status_code=404, detail="Script version not found")
    return sv


@router.get("/{project_id}/narrative", response_model=NarrativeVersionSchema)
async def get_current_narrative(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.current_narrative_version_id:
        raise HTTPException(status_code=404, detail="No narrative generated yet")
    nv = await db.get(NarrativeVersion, project.current_narrative_version_id)
    if nv is None:
        raise HTTPException(status_code=404, detail="Narrative version not found")

    # Enrich scenes with presigned URLs for audio playback
    # Build enriched list WITHOUT mutating the live ORM object to prevent accidental flush
    scenes = list(nv.scenes or [])
    enriched_scenes = []
    for s in scenes:
        audio_key = s.get("audio_key")
        presigned = get_presigned_url(audio_key) if audio_key else None
        enriched_scenes.append({**s, "audio_presigned_url": presigned})

    return NarrativeVersionSchema(
        id=nv.id,
        project_id=nv.project_id,
        version_number=nv.version_number,
        scenes=enriched_scenes,
        fact_checks=nv.fact_checks,
        ai_model=nv.ai_model,
        created_at=nv.created_at,
    )


@router.get("/{project_id}/narrative-versions", response_model=list[NarrativeVersionSchema])
async def list_narrative_versions(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    result = await db.execute(
        select(NarrativeVersion)
        .where(NarrativeVersion.project_id == project_id)
        .order_by(NarrativeVersion.version_number.asc())
    )
    return result.scalars().all()


@router.get("/{project_id}/narrative-versions/{nv_id}", response_model=NarrativeVersionSchema)
async def get_narrative_version(
    project_id: UUID,
    nv_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    nv = await db.get(NarrativeVersion, nv_id)
    if nv is None or nv.project_id != project_id:
        raise HTTPException(status_code=404, detail="Narrative version not found")
    return nv


@router.get("/{project_id}/script-versions", response_model=list[ScriptVersionSchema])
async def list_script_versions(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    result = await db.execute(
        select(ScriptVersion)
        .where(ScriptVersion.project_id == project_id)
        .order_by(ScriptVersion.version_number.asc())
    )
    return result.scalars().all()


@router.get("/{project_id}/script-versions/{sv_id}", response_model=ScriptVersionSchema)
async def get_script_version(
    project_id: UUID,
    sv_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    sv = await db.get(ScriptVersion, sv_id)
    if sv is None or sv.project_id != project_id:
        raise HTTPException(status_code=404, detail="Script version not found")
    return sv


@router.get("/{project_id}/video-url")
async def get_video_url(
    project_id: UUID,
    asset_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    asset = await db.get(VideoAsset, asset_id)
    if asset is None or asset.project_id != project_id:
        raise HTTPException(status_code=404, detail="Video asset not found")

    if not asset.video_file_key:
        raise HTTPException(status_code=404, detail="Video not yet available")

    url = get_presigned_url(asset.video_file_key, expires_seconds=3600)
    return {"url": url, "expires_in": 3600}


@router.post("/{project_id}/performance")
async def record_performance(project_id: UUID, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"POST /api/projects/{project_id}/performance"}


class RegenerateTtsRequest(BaseModel):
    scene_index: int
    narration: str


class RegenerateTtsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)
    audio_key: Optional[str]
    duration_seconds: Optional[float]
    tts_status: str
    presigned_url: Optional[str]


@router.post("/{project_id}/narrative/tts", response_model=RegenerateTtsResponse)
async def regenerate_scene_tts(
    project_id: UUID,
    body: RegenerateTtsRequest,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.current_narrative_version_id:
        raise HTTPException(status_code=404, detail="No narrative version found")

    nv = await db.get(NarrativeVersion, project.current_narrative_version_id)
    if nv is None or not isinstance(nv.scenes, list):
        raise HTTPException(status_code=404, detail="Narrative version scenes not found")

    narration = body.narration.strip()
    scene_idx = body.scene_index

    if not narration:
        scenes = list(nv.scenes)
        found = False
        for i, s in enumerate(scenes):
            if s.get("scene_index") == scene_idx:
                scenes[i] = {**s, "tts_status": "skipped", "audio_key": None, "duration_seconds": None, "narration": narration}
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail=f"Scene {scene_idx} not found in narrative")
        nv.scenes = scenes
        flag_modified(nv, "scenes")
        await db.commit()
        return RegenerateTtsResponse(audio_key=None, duration_seconds=None, tts_status="skipped", presigned_url=None)

    tts_engine = get_tts_engine()
    tts_voice = project.tts_voice
    result = await tts_engine.synthesize(TTSRequest(text=narration, voice=tts_voice))

    if not result.success:
        raise HTTPException(status_code=502, detail=f"TTS failed: {result.error_message}")

    key = f"audio/{project_id}/{nv.id}/scene_{scene_idx}.mp3"

    scenes = list(nv.scenes)
    found = False
    for i, s in enumerate(scenes):
        if s.get("scene_index") == scene_idx:
            scenes[i] = {
                **s,
                "narration": narration,
                "tts_status": "ready",
                "audio_key": key,
                "duration_seconds": result.duration_seconds,
            }
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail=f"Scene {scene_idx} not found in narrative")

    upload_bytes(key, result.audio_bytes, "audio/mpeg")
    nv.scenes = scenes
    flag_modified(nv, "scenes")
    await db.commit()

    presigned = get_presigned_url(key)
    return RegenerateTtsResponse(
        audio_key=key,
        duration_seconds=result.duration_seconds,
        tts_status="ready",
        presigned_url=presigned,
    )
