from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.schemas.project import FactCheckItemSchema


class NarrativeSceneSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    narration: str
    description: str
    estimated_duration_seconds: Optional[float] = None
    audio_key: Optional[str] = None
    duration_seconds: Optional[float] = None
    tts_status: Optional[str] = None
    audio_presigned_url: Optional[str] = None


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
    created_at: datetime
