"""expand project TTS voice name

Revision ID: 7a3d9e5b2c41
Revises: 6e2b8c4f1a90
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a3d9e5b2c41"
down_revision: Union[str, Sequence[str], None] = "6e2b8c4f1a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "video_projects",
        "tts_voice",
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "video_projects",
        "tts_voice",
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
