"""add_narrative_versions

Revision ID: 0aa3661e4fcc
Revises: ec62ee4c1124
Create Date: 2026-06-27 11:56:26.433372

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0aa3661e4fcc'
down_revision: Union[str, Sequence[str], None] = 'ec62ee4c1124'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'narrative_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('scenes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('fact_checks', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ai_model', sa.String(length=50), nullable=True),
        sa.Column('rejection_context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column(
        'video_projects',
        sa.Column('current_narrative_version_id', postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('video_projects', 'current_narrative_version_id')
    op.drop_table('narrative_versions')
