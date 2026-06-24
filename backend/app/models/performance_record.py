import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, Text, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class PerformanceRecord(Base):
    __tablename__ = "performance_records"
    __table_args__ = (UniqueConstraint("project_id", name="uq_performance_records_project_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    views: Mapped[Optional[int]] = mapped_column(Integer)
    completion_rate: Mapped[Optional[float]] = mapped_column(Float)
    likes: Mapped[Optional[int]] = mapped_column(Integer)
    favorites: Mapped[Optional[int]] = mapped_column(Integer)
    comment_tags: Mapped[Optional[list]] = mapped_column(ARRAY(String(30)))
    comment_summary: Mapped[Optional[str]] = mapped_column(Text)
    recorded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
