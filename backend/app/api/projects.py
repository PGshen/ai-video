from fastapi import APIRouter, Depends
from app.auth import verify_api_key

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects(_=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": "GET /api/projects"}


@router.post("")
async def create_project(_=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": "POST /api/projects"}


@router.get("/{project_id}")
async def get_project(project_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"GET /api/projects/{project_id}"}


@router.get("/{project_id}/script-versions")
async def list_script_versions(project_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"GET /api/projects/{project_id}/script-versions"}


@router.get("/{project_id}/events")
async def list_events(project_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"GET /api/projects/{project_id}/events"}


@router.post("/{project_id}/performance")
async def record_performance(project_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"POST /api/projects/{project_id}/performance"}


@router.get("/{project_id}/preview-url")
async def get_preview_url(project_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"GET /api/projects/{project_id}/preview-url"}
