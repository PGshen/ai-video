import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class NarrativeVersion(Base):
    __tablename__ = "narrative_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scenes: Mapped[Optional[list]] = mapped_column(JSONB)
    fact_checks: Mapped[Optional[list]] = mapped_column(JSONB)
    ai_model: Mapped[Optional[str]] = mapped_column(String(50))
    rejection_context: Mapped[Optional[dict]] = mapped_column(JSONB)
    prompt_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
