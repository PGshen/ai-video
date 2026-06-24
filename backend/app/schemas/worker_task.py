from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class WorkerTaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    task_type: str
    engine: Optional[str]
    status: str
    retry_count: int
    max_retries: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class WorkerTaskListResponse(BaseModel):
    items: list[WorkerTaskResponse]
