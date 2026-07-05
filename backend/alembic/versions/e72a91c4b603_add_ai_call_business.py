"""add AI call business

Revision ID: e72a91c4b603
Revises: c41d8a2e7f10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e72a91c4b603"
down_revision: Union[str, Sequence[str], None] = "c41d8a2e7f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_call_records",
        sa.Column(
            "business",
            sa.String(length=50),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.create_index(
        "ix_ai_call_records_business",
        "ai_call_records",
        ["business"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_call_records_business", table_name="ai_call_records")
    op.drop_column("ai_call_records", "business")
