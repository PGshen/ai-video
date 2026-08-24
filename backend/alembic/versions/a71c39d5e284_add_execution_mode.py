"""add execution_mode columns

Revision ID: a71c39d5e284
Revises: 82f4c6a9d731
Create Date: 2026-08-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a71c39d5e284"
down_revision: Union[str, Sequence[str], None] = "82f4c6a9d731"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "video_projects",
        sa.Column("execution_mode", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "ai_business_model_configs",
        sa.Column(
            "execution_mode",
            sa.String(length=20),
            nullable=False,
            server_default="prompt",
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_business_model_configs", "execution_mode")
    op.drop_column("video_projects", "execution_mode")
