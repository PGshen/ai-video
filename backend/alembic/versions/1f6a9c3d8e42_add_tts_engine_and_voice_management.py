"""add TTS engine and voice management

Revision ID: 1f6a9c3d8e42
Revises: 9d4f2c7a8b15
"""

from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "1f6a9c3d8e42"
down_revision: Union[str, Sequence[str], None] = "9d4f2c7a8b15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENGINE_1 = "c1000000-0000-4000-8000-000000000001"
ENGINE_2 = "c1000000-0000-4000-8000-000000000002"


def upgrade() -> None:
    op.create_table(
        "tts_engine_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("provider_type", sa.String(length=30), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_tts_engine_configs_code"),
    )
    op.create_index("ix_tts_engine_configs_code", "tts_engine_configs", ["code"])
    op.create_table(
        "tts_voices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("engine_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("speaker_id", sa.String(length=200), nullable=False),
        sa.Column("language", sa.String(length=30), nullable=False),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("engine_id", "code", name="uq_tts_voices_engine_code"),
    )
    op.create_index("ix_tts_voices_engine_id", "tts_voices", ["engine_id"])

    endpoint = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
    op.execute(sa.text("""
        INSERT INTO tts_engine_configs
            (id, name, code, provider_type, endpoint, api_key, resource_id,
             timeout_seconds, is_active, created_at, updated_at)
        VALUES
            (:id1, '豆包 1.0', 'doubao_1.0', 'volcengine', :endpoint, '',
             'seed-tts-1.0', 60, true, now(), now()),
            (:id2, '豆包 2.0', 'doubao_2.0', 'volcengine', :endpoint, '',
             'seed-tts-2.0', 60, true, now(), now())
    """).bindparams(id1=ENGINE_1, id2=ENGINE_2, endpoint=endpoint))
    voices = [
        ("c2000000-0000-4000-8000-000000000001", ENGINE_1, "思思", "sisi", "zh_female_shuangkuaisisi_moon_bigtts", "female"),
        ("c2000000-0000-4000-8000-000000000002", ENGINE_2, "春日部小姐姐", "xiaoxinjiejie", "zh_female_chunribu_uranus_bigtts", "female"),
        ("c2000000-0000-4000-8000-000000000003", ENGINE_2, "小猪佩奇", "xiaozhupeiqi", "zh_female_peiqi_uranus_bigtts", "female"),
        ("c2000000-0000-4000-8000-000000000004", ENGINE_2, "清澈梓梓", "zizi", "zh_female_qingchezizi_uranus_bigtts", "female"),
        ("c2000000-0000-4000-8000-000000000005", ENGINE_2, "云舟", "yunzhou", "zh_male_m191_uranus_bigtts", "male"),
        ("c2000000-0000-4000-8000-000000000006", ENGINE_2, "小禾", "xiaohe", "zh_female_xiaohe_uranus_bigtts", "female"),
    ]
    voice_table = sa.table(
        "tts_voices",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("engine_id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String()), sa.column("code", sa.String()),
        sa.column("speaker_id", sa.String()), sa.column("language", sa.String()),
        sa.column("gender", sa.String()), sa.column("description", sa.String()),
        sa.column("is_active", sa.Boolean()), sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(voice_table, [
        {"id": row[0], "engine_id": row[1], "name": row[2], "code": row[3],
         "speaker_id": row[4], "language": "zh-CN", "gender": row[5],
         "description": None, "is_active": True,
         "created_at": now, "updated_at": now}
        for row in voices
    ])


def downgrade() -> None:
    op.drop_index("ix_tts_voices_engine_id", table_name="tts_voices")
    op.drop_table("tts_voices")
    op.drop_index("ix_tts_engine_configs_code", table_name="tts_engine_configs")
    op.drop_table("tts_engine_configs")
