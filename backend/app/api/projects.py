from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from temporalio.client import Client as TemporalClient, WorkflowExecutionStatus
from app.auth import verify_api_key
from app.db import get_async_session
from app.deps import get_temporal_client
from app.models.project import VideoProject
from app.models.prompt_component import PromptComponent
from app.models.script_version import ScriptVersion
from app.models.narrative_version import NarrativeVersion
from app.schemas.narrative import NarrativeBeatSchema, NarrativeVersionSchema
from app.models.topic import Topic
from app.models.project_event import ProjectEvent
from app.models.video_asset import VideoAsset
from app.models.worker_task import WorkerTask
from app.models.performance_record import PerformanceRecord
from app.storage import get_presigned_url, upload_bytes
from app.engines.tts.factory import get_tts_engine
from app.engines.tts.base import TTSRequest
from app.engines.ai.factory import get_ai_provider
from app.schemas.project import (
    ProjectCreate, ProjectResponse, ProjectListResponse,
    ProjectDetailResponse, EventListResponse, ScriptVersionSchema,
    CodeRepairRequest, CodeRepairResponse,
)
from app.workflows.video_production import VideoProductionWorkflow
from app.config import settings
from app.services.beat_aligner import align_scene_beats
from app.services.narrative_validator import validate_and_normalize_scenes
from app.services.prompt_bundle import style_components_from_snapshot

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
    topic_id: Optional[UUID] = None,
    topic_title: Optional[str] = None,
    render_engine: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    stmt = select(VideoProject)
    if status:
        stmt = stmt.where(VideoProject.status == status)
    if topic_id:
        stmt = stmt.where(VideoProject.topic_id == topic_id)
    if topic_title and topic_title.strip():
        matching_topics = select(Topic.id).where(
            Topic.title.ilike(f"%{topic_title.strip()}%")
        )
        stmt = stmt.where(VideoProject.topic_id.in_(matching_topics))
    if render_engine:
        stmt = stmt.where(VideoProject.render_engine == render_engine)
    if aspect_ratio:
        stmt = stmt.where(VideoProject.aspect_ratio == aspect_ratio)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        stmt.order_by(VideoProject.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
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

    return ProjectListResponse(items=items, total=total)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    temporal: TemporalClient = Depends(get_temporal_client),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Temporal is authoritative for workflow state; only terminate a live run.
    if project.temporal_workflow_id:
        handle = temporal.get_workflow_handle(project.temporal_workflow_id)
        try:
            description = await handle.describe()
            if description.status == WorkflowExecutionStatus.RUNNING:
                await handle.terminate(reason="Project deleted by user")
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="无法停止项目工作流，请稍后重试",
            ) from exc

    # The schema intentionally has no foreign keys, so maintain associations here.
    for model in (
        WorkerTask,
        ProjectEvent,
        PerformanceRecord,
        VideoAsset,
        ScriptVersion,
        NarrativeVersion,
    ):
        await db.execute(delete(model).where(model.project_id == project_id))
    await db.delete(project)

    await db.commit()


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

    if body.style_config:
        for category, component_id in body.style_config.items():
            try:
                comp_uuid = _uuid.UUID(str(component_id))
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail=f"style_config[{category}]: invalid UUID")
            comp = await db.get(PromptComponent, comp_uuid)
            if comp is None:
                raise HTTPException(status_code=422, detail=f"style_config[{category}]: component not found")

    project_id = _uuid.uuid4()
    workflow_id = f"video-production-{project_id}"

    orm_project = VideoProject(
        topic_id=body.topic_id,
        status="draft",
        render_engine=body.render_engine,
        tts_voice=body.tts_voice,
        aspect_ratio=body.aspect_ratio,
        temporal_workflow_id=workflow_id,
        narrative_context=body.narrative_context,
        style_config=body.style_config,
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
    ).order_by(ProjectEvent.created_at.asc(), ProjectEvent.id.asc())
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


@router.post("/{project_id}/script/repair", response_model=CodeRepairResponse)
async def repair_script_code(
    project_id: UUID,
    body: CodeRepairRequest,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != "script_review":
        raise HTTPException(
            status_code=409,
            detail="Code repair is only available during script review",
        )
    if not body.error_message.strip():
        raise HTTPException(status_code=422, detail="Render error message is required")
    if not body.scenes:
        raise HTTPException(status_code=422, detail="At least one scene is required")

    scene_indices = [scene.scene_index for scene in body.scenes]
    if len(scene_indices) != len(set(scene_indices)):
        raise HTTPException(status_code=422, detail="Scene indices must be unique")

    provider = get_ai_provider()
    script_version = (
        await db.get(ScriptVersion, project.current_script_version_id)
        if project.current_script_version_id
        else None
    )
    if script_version is None or not isinstance(script_version.prompt_snapshot, dict):
        raise HTTPException(status_code=409, detail="Script version has no prompt snapshot")
    try:
        style_components = style_components_from_snapshot(script_version.prompt_snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        result = await provider.repair_code(
            scenes=[scene.model_dump() for scene in body.scenes],
            render_engine=project.render_engine,
            error_message=body.error_message,
            style_components=style_components,
            aspect_ratio=project.aspect_ratio,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI code repair failed: {exc}") from exc
    return CodeRepairResponse(repairs=result.repairs)


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
        prompt_snapshot=nv.prompt_snapshot,
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
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    narration: str
    beats: list[NarrativeBeatSchema]


class RegenerateTtsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)
    audio_key: Optional[str]
    duration_seconds: Optional[float]
    tts_status: str
    presigned_url: Optional[str]
    beats: list[NarrativeBeatSchema] = Field(default_factory=list)
    alignment_coverage: Optional[float] = None


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
        raise HTTPException(status_code=422, detail="Narration must be non-empty")

    source_scene = next(
        (scene for scene in nv.scenes if scene.get("scene_index") == scene_idx),
        None,
    )
    if source_scene is None:
        raise HTTPException(status_code=404, detail=f"Scene {scene_idx} not found in narrative")

    candidate_scene = {
        **source_scene,
        "narration": narration,
        "beats": [beat.model_dump() for beat in body.beats],
    }
    try:
        validated_scene = validate_and_normalize_scenes(
            [{**candidate_scene, "scene_index": 0}]
        )[0]
        validated_scene["scene_index"] = scene_idx
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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
            scene_with_audio = {
                **validated_scene,
                "tts_status": "ready",
                "audio_key": key,
                "duration_seconds": result.duration_seconds,
                "word_timestamps": [
                    {
                        "word": item.word,
                        "start_time": item.start_time,
                        "end_time": item.end_time,
                        "confidence": item.confidence,
                    }
                    for item in result.word_timestamps
                ],
            }
            scenes[i] = align_scene_beats(scene_with_audio)
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
        beats=scenes[i]["beats"],
        alignment_coverage=scenes[i].get("alignment_coverage"),
    )
