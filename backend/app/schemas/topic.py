from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Optional
from datetime import datetime
from uuid import UUID


class TopicScores(BaseModel):
    counterintuitive: Optional[int] = Field(None, ge=1, le=5)
    defensibility: Optional[int] = Field(None, ge=1, le=5)
    visual: Optional[int] = Field(None, ge=1, le=5)
    freshness: Optional[int] = Field(None, ge=1, le=5)


class TopicBase(BaseModel):
    title: str
    description: Optional[str] = None
    source: str
    tags: list[str] = []
    scores: TopicScores = TopicScores()


class TopicCreate(TopicBase):
    pass


class TopicUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[list[str]] = None
    scores: Optional[TopicScores] = None
    status: Optional[str] = None


class TopicResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )

    id: UUID
    title: str
    description: Optional[str]
    source: str
    status: str
    score_counterintuitive: Optional[int] = None
    score_defensibility: Optional[int] = None
    score_visual: Optional[int] = None
    score_freshness: Optional[int] = None
    composite_score: Optional[float] = None
    performance_score: Optional[float] = None
    tags: list[str] = []
    needs_recheck: bool
    research_data: list[dict] = []
    created_at: datetime
    updated_at: datetime


class TopicListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)
    items: list[TopicResponse]
    total: int


class ResearchMessageRequest(BaseModel):
    message: str = ""
    use_default_prompt: bool = False


class BrainstormRequest(BaseModel):
    topic_direction: str
    count: int = Field(default=5, ge=1, le=20)


class BrainstormResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)
    candidates: list[dict]
