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
from app.services.narrative_validator import (
    validate_and_normalize_scenes,
    validate_scenes_for_codegen,
)

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
        reviewed_version = None
        if project.current_narrative_version_id:
            nv = await db.get(NarrativeVersion, project.current_narrative_version_id)
            reviewed_version = nv
            if body.edited_scenes and nv and isinstance(nv.scenes, list):
                edited_map = {s.scene_index: s for s in body.edited_scenes}
                updated_scenes = []
                for scene in nv.scenes:
                    idx = scene.get("scene_index", -1)
                    if idx in edited_map:
                        edit = edited_map[idx]
                        persisted_cues = [
                            beat.get("cue_text")
                            for beat in scene.get("beats") or []
                        ]
                        edited_cues = [beat.cue_text for beat in edit.beats]
                        if edited_cues != persisted_cues:
                            raise HTTPException(
                                status_code=409,
                                detail=(
                                    f"Scene {idx} narration beats changed without regenerated TTS"
                                ),
                            )
                        updated_scenes.append({
                            **scene,
                            "narration": edit.narration,
                            "description": edit.description,
                            "beats": [beat.model_dump() for beat in edit.beats],
                            **({"estimated_duration_seconds": edit.estimated_duration_seconds}
                               if edit.estimated_duration_seconds is not None else {}),
                        })
                    else:
                        updated_scenes.append(scene)
                try:
                    updated_scenes = validate_and_normalize_scenes(
                        updated_scenes,
                        preserve_alignment=True,
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
                if body.verdict == "approved":
                    try:
                        validate_scenes_for_codegen(updated_scenes)
                    except ValueError as exc:
                        raise HTTPException(status_code=422, detail=str(exc)) from exc
                new_nv = NarrativeVersion(
                    project_id=nv.project_id,
                    version_number=nv.version_number + 1,
                    scenes=updated_scenes,
                    fact_checks=nv.fact_checks,
                    ai_model=nv.ai_model,
                    rejection_context=nv.rejection_context,
                    prompt_snapshot=nv.prompt_snapshot,
                )
                db.add(new_nv)
                await db.flush()
                project.current_narrative_version_id = new_nv.id
                reviewed_version = new_nv
                await db.commit()
            elif body.verdict == "approved" and nv and isinstance(nv.scenes, list):
                try:
                    validate_scenes_for_codegen(list(nv.scenes))
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc

        signal_name = "narrative_review"

    elif body.gate == "script":
        sv = await db.get(ScriptVersion, project.current_script_version_id)
        reviewed_version = sv
        if sv:
            has_edits = bool(body.fact_check_verdicts or body.edited_script_scenes)
            if has_edits:
                fact_checks = list(sv.fact_checks) if isinstance(sv.fact_checks, list) else (sv.fact_checks or [])
                if body.fact_check_verdicts:
                    for v in body.fact_check_verdicts:
                        if 0 <= v.index < len(fact_checks):
                            fact_checks[v.index] = {
                                **dict(fact_checks[v.index]),
                                "reviewer_verdict": v.verdict,
                                "reviewer_note": v.note or None,
                            }
                scenes = list(sv.scenes) if isinstance(sv.scenes, list) else (sv.scenes or [])
                if body.edited_script_scenes:
                    code_map = {s.scene_index: s.code for s in body.edited_script_scenes}
                    for i, scene in enumerate(scenes):
                        idx = scene.get("scene_index", -1)
                        if idx in code_map:
                            scenes[i] = {**scene, "code": code_map[idx]}
                new_sv = ScriptVersion(
                    project_id=sv.project_id,
                    version_number=sv.version_number + 1,
                    scenes=scenes,
                    fact_checks=fact_checks,
                    render_engine=sv.render_engine,
                    ai_model=sv.ai_model,
                    rejection_context=sv.rejection_context,
                    prompt_snapshot=sv.prompt_snapshot,
                )
                db.add(new_sv)
                await db.flush()
                project.current_script_version_id = new_sv.id
                reviewed_version = new_sv
                await db.commit()

        signal_name = "script_review"

    else:
        reviewed_version = None
        signal_name = "video_review"
    signal_payload = {
        "verdict": body.verdict,
        "rejection_type": body.rejection_type,
        "rejection_detail": body.rejection_detail,
        "target_stage": body.target_stage,
    }

    # 只有 Temporal 成功接收操作后才记录结果，避免时间线出现“假成功”。
    review_status = project.status
    handle = temporal.get_workflow_handle(project.temporal_workflow_id)
    await handle.signal(signal_name, signal_payload)

    # Persist review verdict and its exact content version for timeline history.
    event_payload: dict = {"gate": body.gate, "verdict": body.verdict}
    if body.rejection_type:
        event_payload["rejection_type"] = body.rejection_type
    if body.rejection_detail:
        event_payload["rejection_detail"] = body.rejection_detail
    if body.target_stage:
        event_payload["target_stage"] = body.target_stage
    if reviewed_version is not None:
        event_payload["content_version_id"] = str(reviewed_version.id)
        event_payload["content_version_number"] = reviewed_version.version_number
    db.add(ProjectEvent(
        project_id=project_id,
        event_type="review_verdict",
        from_status=review_status,
        to_status=None,
        actor="reviewer",
        payload=event_payload,
    ))
    await db.commit()
    return {"status": "ok"}
