"""remove topic production status

Revision ID: 2cde51a4b780
Revises: 36b73e58f8a1
"""

from typing import Sequence, Union

from alembic import op


revision: str = "2cde51a4b780"
down_revision: Union[str, Sequence[str], None] = "36b73e58f8a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE topics SET status = 'stocked' WHERE status = 'in_production'"
    )


def downgrade() -> None:
    # Production state cannot be reconstructed reliably from topic data.
    pass
