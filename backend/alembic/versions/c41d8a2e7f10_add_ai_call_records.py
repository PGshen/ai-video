"""add AI call records

Revision ID: c41d8a2e7f10
Revises: a6f4d8c91e20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c41d8a2e7f10"
down_revision: Union[str, Sequence[str], None] = "a6f4d8c91e20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_call_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("request_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("input_cost", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("output_cost", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("total_cost", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(length=200), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_call_records_provider", "ai_call_records", ["provider"])
    op.create_index("ix_ai_call_records_model", "ai_call_records", ["model"])
    op.create_index("ix_ai_call_records_status", "ai_call_records", ["status"])
    op.create_index("ix_ai_call_records_started_at", "ai_call_records", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_call_records_started_at", table_name="ai_call_records")
    op.drop_index("ix_ai_call_records_status", table_name="ai_call_records")
    op.drop_index("ix_ai_call_records_model", table_name="ai_call_records")
    op.drop_index("ix_ai_call_records_provider", table_name="ai_call_records")
    op.drop_table("ai_call_records")
