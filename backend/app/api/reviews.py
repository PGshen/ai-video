from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from temporalio.client import Client as TemporalClient
from app.auth import verify_api_key
from app.db import get_async_session
from app.deps import get_temporal_client
from app.models.project import VideoProject
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

    # 写回 fact_check verdicts（仅 script gate 且有标注数据时）
    if body.gate == "script" and body.fact_check_verdicts:
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

    signal_name = "script_review" if body.gate == "script" else "video_review"
    payload = {
        "verdict": body.verdict,
        "rejection_type": body.rejection_type,
        "rejection_detail": body.rejection_detail,
        "target_stage": body.target_stage,
    }

    handle = temporal.get_workflow_handle(project.temporal_workflow_id)
    await handle.signal(signal_name, payload)
    return {"status": "ok"}
