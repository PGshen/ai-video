from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class ProjectCreate(BaseModel):
    topic_id: UUID
    render_engine: str
    tts_voice: str
    aspect_ratio: str


class SceneSchema(BaseModel):
    scene_index: int
    narration: str
    description: str
    code: str
    estimated_duration_seconds: float


class FactCheckItemSchema(BaseModel):
    claim_text: str
    scene_index: int
    source_url: Optional[str]
    source_description: str
    confidence: str
    is_hypothesis: bool
    assumptions: Optional[str]
    controversy: Optional[str]
    reviewer_verdict: Optional[str]
    reviewer_note: Optional[str]


class ScriptVersionSchema(BaseModel):
    id: UUID
    project_id: UUID
    version_number: int
    scenes: Optional[list[SceneSchema]]
    fact_checks: Optional[list[FactCheckItemSchema]]
    render_engine: str
    ai_model: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoAssetSchema(BaseModel):
    id: UUID
    project_id: UUID
    video_file_key: Optional[str]
    duration_seconds: Optional[float]
    resolution: Optional[str]
    status: str

    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    id: UUID
    topic_id: UUID
    status: str
    render_engine: str
    tts_voice: str
    aspect_ratio: str
    retry_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetailResponse(ProjectResponse):
    current_script_version: Optional[ScriptVersionSchema]
    current_video_asset: Optional[VideoAssetSchema]


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int


class ScriptVersionListResponse(BaseModel):
    items: list[ScriptVersionSchema]


class EventSchema(BaseModel):
    id: int
    project_id: UUID
    event_type: str
    from_status: Optional[str]
    to_status: Optional[str]
    actor: str
    payload: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    items: list[EventSchema]


class PerformanceCreate(BaseModel):
    platform: str
    views: Optional[int] = None
    completion_rate: Optional[float] = None
    likes: Optional[int] = None
    favorites: Optional[int] = None
    comment_tags: list[str] = []
    comment_summary: Optional[str] = None


class PerformanceResponse(BaseModel):
    id: UUID
    project_id: UUID
    platform: str
    views: Optional[int]
    completion_rate: Optional[float]
    likes: Optional[int]
    favorites: Optional[int]
    comment_tags: list[str]
    comment_summary: Optional[str]

    model_config = {"from_attributes": True}


class PreviewUrlResponse(BaseModel):
    url: str
    expires_in_seconds: int
