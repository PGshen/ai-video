from pydantic import BaseModel, Field
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
    id: UUID
    title: str
    description: Optional[str]
    source: str
    status: str
    scores: TopicScores
    composite_score: Optional[float]
    performance_score: Optional[float]
    tags: list[str]
    needs_recheck: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TopicListResponse(BaseModel):
    items: list[TopicResponse]
    total: int


class BrainstormRequest(BaseModel):
    topic_direction: str
    count: int = Field(default=5, ge=1, le=20)


class BrainstormResponse(BaseModel):
    candidates: list[dict]
