import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, SmallInteger, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class WorkerTask(Base):
    __tablename__ = "worker_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True)
    )
    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    engine: Mapped[Optional[str]] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    input_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    output_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    max_retries: Mapped[int] = mapped_column(SmallInteger, default=3)
    temporal_workflow_id: Mapped[Optional[str]] = mapped_column(String(100))
    signal_name: Mapped[Optional[str]] = mapped_column(String(50))
    worker_id: Mapped[Optional[str]] = mapped_column(String(100))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
