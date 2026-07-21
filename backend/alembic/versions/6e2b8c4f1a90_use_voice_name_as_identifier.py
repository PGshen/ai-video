"""use TTS voice name as identifier

Revision ID: 6e2b8c4f1a90
Revises: 1f6a9c3d8e42
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6e2b8c4f1a90"
down_revision: Union[str, Sequence[str], None] = "1f6a9c3d8e42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Projects previously stored the per-engine voice code. Convert every known
    # reference to the voice name before removing the intermediate field.
    op.execute(sa.text("""
        UPDATE video_projects AS project
        SET tts_voice = voice.name
        FROM tts_engine_configs AS engine, tts_voices AS voice
        WHERE voice.engine_id = engine.id
          AND project.tts_engine = engine.code
          AND project.tts_voice = voice.code
    """))
    op.drop_constraint("uq_tts_voices_engine_code", "tts_voices", type_="unique")
    op.create_unique_constraint(
        "uq_tts_voices_engine_name", "tts_voices", ["engine_id", "name"]
    )
    op.drop_column("tts_voices", "code")


def downgrade() -> None:
    op.add_column("tts_voices", sa.Column("code", sa.String(length=50), nullable=True))
    op.execute(sa.text("""
        UPDATE tts_voices
        SET code = 'voice_' || replace(id::text, '-', '')
    """))
    op.execute(sa.text("""
        UPDATE video_projects AS project
        SET tts_voice = voice.code
        FROM tts_engine_configs AS engine, tts_voices AS voice
        WHERE voice.engine_id = engine.id
          AND project.tts_engine = engine.code
          AND project.tts_voice = voice.name
    """))
    op.alter_column("tts_voices", "code", nullable=False)
    op.drop_constraint("uq_tts_voices_engine_name", "tts_voices", type_="unique")
    op.create_unique_constraint(
        "uq_tts_voices_engine_code", "tts_voices", ["engine_id", "code"]
    )
