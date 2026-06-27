"""add_render_log_to_video_assets

Revision ID: 4b8e2f980c54
Revises: 0aa3661e4fcc
Create Date: 2026-06-27 18:33:41.961182

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b8e2f980c54'
down_revision: Union[str, Sequence[str], None] = '0aa3661e4fcc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('video_assets', sa.Column('render_log', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('video_assets', 'render_log')
