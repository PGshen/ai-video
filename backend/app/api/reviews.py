from fastapi import APIRouter, Depends
from app.auth import verify_api_key

router = APIRouter(prefix="/api/projects", tags=["reviews"])


@router.post("/{project_id}/review")
async def submit_review(project_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"POST /api/projects/{project_id}/review"}
