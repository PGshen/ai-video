from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import BigInteger, String, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base
import uuid


def utcnow():
    return datetime.now(timezone.utc)


class ProjectEvent(Base):
    __tablename__ = "project_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(30))
    to_status: Mapped[Optional[str]] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
