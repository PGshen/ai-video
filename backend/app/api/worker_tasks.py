from fastapi import APIRouter, Depends
from app.auth import verify_api_key

router = APIRouter(prefix="/api/worker-tasks", tags=["worker-tasks"])


@router.get("")
async def list_worker_tasks(_=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": "GET /api/worker-tasks"}
