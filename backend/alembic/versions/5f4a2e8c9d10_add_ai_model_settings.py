"""add ai model settings

Revision ID: 5f4a2e8c9d10
Revises: c7e2a94f1d38
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "5f4a2e8c9d10"
down_revision: Union[str, Sequence[str], None] = "c7e2a94f1d38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_model_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("provider_type", sa.String(length=30), nullable=False),
        sa.Column("base_url", sa.String(length=300), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("site_url", sa.String(length=300), nullable=True),
        sa.Column("site_name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_model_providers_provider_type",
        "ai_model_providers",
        ["provider_type"],
    )

    op.create_table(
        "ai_provider_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("content_max_tokens", sa.Integer(), nullable=False),
        sa.Column("json_max_tokens", sa.Integer(), nullable=False),
        sa.Column("input_cost_per_million", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("cached_input_cost_per_million", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("output_cost_per_million", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_provider_models_provider_id", "ai_provider_models", ["provider_id"])
    op.create_index("ix_ai_provider_models_model", "ai_provider_models", ["model"])

    op.create_table(
        "ai_business_model_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business", sa.String(length=50), nullable=False),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business"),
    )
    op.create_index(
        "ix_ai_business_model_configs_business",
        "ai_business_model_configs",
        ["business"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_business_model_configs_business",
        table_name="ai_business_model_configs",
    )
    op.drop_table("ai_business_model_configs")
    op.drop_index("ix_ai_provider_models_model", table_name="ai_provider_models")
    op.drop_index("ix_ai_provider_models_provider_id", table_name="ai_provider_models")
    op.drop_table("ai_provider_models")
    op.drop_index(
        "ix_ai_model_providers_provider_type",
        table_name="ai_model_providers",
    )
    op.drop_table("ai_model_providers")
