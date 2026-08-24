import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIModelProvider(Base):
    __tablename__ = "ai_model_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(300), nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    timeout_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=600.0)
    site_url: Mapped[str | None] = mapped_column(String(300))
    site_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class AIProviderModel(Base):
    __tablename__ = "ai_provider_models"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    content_max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=100000)
    json_max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=100000)
    input_cost_per_million: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=0
    )
    cached_input_cost_per_million: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=0
    )
    output_cost_per_million: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=0
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class AIBusinessModelConfig(Base):
    __tablename__ = "ai_business_model_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    business: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    model_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    execution_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="prompt", server_default="prompt"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
