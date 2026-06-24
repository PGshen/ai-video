from fastapi import APIRouter, Depends
from app.auth import verify_api_key

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("")
async def list_topics(_=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": "GET /api/topics"}


@router.post("")
async def create_topic(_=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": "POST /api/topics"}


@router.post("/brainstorm")
async def brainstorm_topics(_=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": "POST /api/topics/brainstorm"}


@router.patch("/{topic_id}")
async def update_topic(topic_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"PATCH /api/topics/{topic_id}"}
