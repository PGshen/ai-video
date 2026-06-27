from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from temporalio.client import Client as TemporalClient
from app.auth import verify_api_key
from app.db import get_async_session
from app.deps import get_temporal_client
from app.models.project import VideoProject
from app.models.narrative_version import NarrativeVersion
from app.models.project_event import ProjectEvent
from app.models.script_version import ScriptVersion
from app.schemas.review import ReviewRequest

router = APIRouter(prefix="/api/projects", tags=["reviews"])


@router.post("/{project_id}/review")
async def submit_review(
    project_id: UUID,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_async_session),
    temporal: TemporalClient = Depends(get_temporal_client),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.temporal_workflow_id:
        raise HTTPException(status_code=400, detail="Project has no active workflow")

    if body.gate == "narrative":
        # 若有内联编辑，更新叙事版本的 scenes
        if body.edited_scenes and project.current_narrative_version_id:
            nv = await db.get(NarrativeVersion, project.current_narrative_version_id)
            if nv and isinstance(nv.scenes, list):
                edited_map = {s.scene_index: s for s in body.edited_scenes}
                updated_scenes = []
                for scene in nv.scenes:
                    idx = scene.get("scene_index", -1)
                    if idx in edited_map:
                        edit = edited_map[idx]
                        updated_scenes.append({
                            **scene,
                            "narration": edit.narration,
                            "description": edit.description,
                            **({"estimated_duration_seconds": edit.estimated_duration_seconds}
                               if edit.estimated_duration_seconds is not None else {}),
                        })
                    else:
                        updated_scenes.append(scene)
                nv.scenes = updated_scenes
                flag_modified(nv, "scenes")
                await db.commit()

        signal_name = "narrative_review"

    elif body.gate == "script":
        # 写回 fact_check verdicts（仅有标注数据时）
        if body.fact_check_verdicts:
            sv = await db.get(ScriptVersion, project.current_script_version_id)
            if sv and isinstance(sv.fact_checks, list):
                fact_checks = list(sv.fact_checks)
                for v in body.fact_check_verdicts:
                    if 0 <= v.index < len(fact_checks):
                        fact_checks[v.index] = {
                            **dict(fact_checks[v.index]),
                            "reviewer_verdict": v.verdict,
                            "reviewer_note": v.note or None,
                        }
                sv.fact_checks = fact_checks
                flag_modified(sv, "fact_checks")
                await db.commit()

        signal_name = "script_review"

    else:
        signal_name = "video_review"
    signal_payload = {
        "verdict": body.verdict,
        "rejection_type": body.rejection_type,
        "rejection_detail": body.rejection_detail,
        "target_stage": body.target_stage,
    }

    # Persist review verdict as a project event for timeline display
    event_payload: dict = {"gate": body.gate, "verdict": body.verdict}
    if body.rejection_detail:
        event_payload["rejection_detail"] = body.rejection_detail
    if body.target_stage:
        event_payload["target_stage"] = body.target_stage
    db.add(ProjectEvent(
        project_id=project_id,
        event_type="review_verdict",
        from_status=project.status,
        to_status=None,
        actor="reviewer",
        payload=event_payload,
    ))
    await db.commit()

    handle = temporal.get_workflow_handle(project.temporal_workflow_id)
    await handle.signal(signal_name, signal_payload)
    return {"status": "ok"}
