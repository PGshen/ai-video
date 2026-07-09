from fastapi import APIRouter, Depends
from app.auth import require_active_user

router = APIRouter(prefix="/api/worker-tasks", tags=["worker-tasks"])


@router.get("")
async def list_worker_tasks(_=Depends(require_active_user)):
    return {"status": "TODO", "endpoint": "GET /api/worker-tasks"}
