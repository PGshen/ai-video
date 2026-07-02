from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.schemas.beat import NarrativeBeatSchema
from app.schemas.project import FactCheckItemSchema


class WordTimestampSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    word: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None


class NarrativeSceneSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    narration: str
    description: str
    beats: list[NarrativeBeatSchema]
    estimated_duration_seconds: Optional[float] = None
    audio_key: Optional[str] = None
    duration_seconds: Optional[float] = None
    tts_status: Optional[str] = None
    audio_presigned_url: Optional[str] = None
    word_timestamps: list[WordTimestampSchema] = Field(default_factory=list)
    alignment_coverage: Optional[float] = None
    content_schema_version: int = 2


class NarrativeVersionSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, alias_generator=to_camel
    )

    id: UUID
    project_id: UUID
    version_number: int
    scenes: Optional[list[NarrativeSceneSchema]]
    fact_checks: Optional[list[FactCheckItemSchema]]
    ai_model: Optional[str]
    prompt_snapshot: Optional[dict] = None
    created_at: datetime
