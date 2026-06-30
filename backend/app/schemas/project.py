from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Optional
from datetime import datetime
from uuid import UUID


class ProjectCreate(BaseModel):
    topic_id: UUID
    render_engine: str
    tts_voice: str
    aspect_ratio: str
    narrative_context: list[dict] = []


class SceneSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
    )

    scene_index: int
    narration: str
    description: str
    code: str
    estimated_duration_seconds: Optional[float] = None


class FactCheckItemSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
    )

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
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )

    id: UUID
    project_id: UUID
    version_number: int
    scenes: Optional[list[SceneSchema]]
    fact_checks: Optional[list[FactCheckItemSchema]]
    render_engine: str
    ai_model: Optional[str]
    created_at: datetime


class VideoAssetSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )

    id: UUID
    project_id: UUID
    video_file_key: Optional[str]
    duration_seconds: Optional[float]
    resolution: Optional[str]
    render_log: Optional[str]
    error_message: Optional[str]
    status: str


class ProjectResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )
    id: UUID
    topic_id: UUID
    topic_title: str = ""
    status: str
    render_engine: str
    tts_voice: str
    aspect_ratio: str
    retry_count: int
    created_at: datetime
    updated_at: datetime


class ProjectDetailResponse(ProjectResponse):
    current_script_version: Optional[ScriptVersionSchema]
    current_video_asset: Optional[VideoAssetSchema]


class ProjectListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)
    items: list[ProjectResponse]
    total: int


class ScriptVersionListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)
    items: list[ScriptVersionSchema]


class CodeRepairSceneInput(SceneSchema):
    pass


class CodeRepairRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    error_message: str
    scenes: list[CodeRepairSceneInput]


class CodeRepairItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    code: str
    explanation: str


class CodeRepairResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    repairs: list[CodeRepairItem]


class EventSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )
    id: int
    project_id: UUID
    event_type: str
    from_status: Optional[str]
    to_status: Optional[str]
    actor: str
    payload: Optional[dict]
    created_at: datetime


class EventListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)
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
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )
    id: UUID
    project_id: UUID
    platform: str
    views: Optional[int]
    completion_rate: Optional[float]
    likes: Optional[int]
    favorites: Optional[int]
    comment_tags: list[str]
    comment_summary: Optional[str]


class PreviewUrlResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)
    url: str
    expires_in_seconds: int
