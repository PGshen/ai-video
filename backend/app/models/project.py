import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, SmallInteger, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class VideoProject(Base):
    __tablename__ = "video_projects"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    render_engine: Mapped[str] = mapped_column(String(20), nullable=False)
    tts_voice: Mapped[str] = mapped_column(String(50), nullable=False)
    tts_engine: Mapped[str] = mapped_column(
        String(30), nullable=False, default="doubao_2.0", server_default="doubao_2.0"
    )
    tts_speed: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1.0"
    )
    aspect_ratio: Mapped[str] = mapped_column(String(20), nullable=False)
    current_code_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True)
    )
    current_video_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True)
    )
    current_narrative_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True)
    )
    temporal_workflow_id: Mapped[Optional[str]] = mapped_column(String(100))
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    narrative_context: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    style_config: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
