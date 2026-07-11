"""add project TTS engine and speed settings

Revision ID: aa7b3d9e4f21
Revises: 9b1c2d3e4f5a
Create Date: 2026-07-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "aa7b3d9e4f21"
down_revision: Union[str, Sequence[str], None] = "9b1c2d3e4f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "video_projects",
        sa.Column("tts_engine", sa.String(length=30), nullable=False, server_default="doubao_2.0"),
    )
    op.add_column(
        "video_projects",
        sa.Column("tts_speed", sa.Float(), nullable=False, server_default="1.0"),
    )


def downgrade() -> None:
    op.drop_column("video_projects", "tts_speed")
    op.drop_column("video_projects", "tts_engine")
