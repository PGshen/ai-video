"""add_research_data_to_topics

Revision ID: ec62ee4c1124
Revises: d9a1b815b39b
Create Date: 2026-06-26 12:57:37.826089

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'ec62ee4c1124'
down_revision: Union[str, Sequence[str], None] = 'd9a1b815b39b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column("research_data", JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("topics", "research_data")
