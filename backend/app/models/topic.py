import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, SmallInteger, Float, Boolean, Computed, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Topic(Base):
    def __init__(self, **kwargs):
        kwargs.setdefault("id", uuid.uuid4())
        kwargs.setdefault("status", "pending")
        kwargs.setdefault("needs_recheck", False)
        kwargs.setdefault("research_data", [])
        now = utcnow()
        kwargs.setdefault("created_at", now)
        kwargs.setdefault("updated_at", now)
        super().__init__(**kwargs)

    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    score_counterintuitive: Mapped[Optional[int]] = mapped_column(SmallInteger)
    score_defensibility: Mapped[Optional[int]] = mapped_column(SmallInteger)
    score_visual: Mapped[Optional[int]] = mapped_column(SmallInteger)
    score_freshness: Mapped[Optional[int]] = mapped_column(SmallInteger)
    composite_score: Mapped[Optional[float]] = mapped_column(
        Float,
        Computed(
            "(score_counterintuitive + score_defensibility + score_visual + score_freshness) / 4.0",
            persisted=True,
        ),
    )
    performance_score: Mapped[Optional[float]] = mapped_column(Float)
    tags: Mapped[Optional[list]] = mapped_column(ARRAY(String(50)))
    needs_recheck: Mapped[bool] = mapped_column(Boolean, default=False)
    research_data: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
