"""rename script domain to code

Revision ID: a6f4d8c91e20
Revises: 3e9d7c2b5a1f
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a6f4d8c91e20"
down_revision: Union[str, Sequence[str], None] = "3e9d7c2b5a1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_script_versions_project_id")
    op.rename_table("script_versions", "code_versions")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_code_versions_project_id "
        "ON code_versions (project_id)"
    )

    op.alter_column(
        "video_projects",
        "current_script_version_id",
        new_column_name="current_code_version_id",
    )
    op.alter_column(
        "worker_tasks",
        "script_version_id",
        new_column_name="code_version_id",
    )
    op.alter_column(
        "video_assets",
        "script_version_id",
        new_column_name="code_version_id",
    )

    op.execute(
        "UPDATE video_projects SET status = 'code_review' "
        "WHERE status = 'script_review'"
    )
    op.execute(
        "UPDATE project_events SET from_status = 'code_review' "
        "WHERE from_status = 'script_review'"
    )
    op.execute(
        "UPDATE project_events SET to_status = 'code_review' "
        "WHERE to_status = 'script_review'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE project_events SET to_status = 'script_review' "
        "WHERE to_status = 'code_review'"
    )
    op.execute(
        "UPDATE project_events SET from_status = 'script_review' "
        "WHERE from_status = 'code_review'"
    )
    op.execute(
        "UPDATE video_projects SET status = 'script_review' "
        "WHERE status = 'code_review'"
    )

    op.alter_column(
        "video_assets",
        "code_version_id",
        new_column_name="script_version_id",
    )
    op.alter_column(
        "worker_tasks",
        "code_version_id",
        new_column_name="script_version_id",
    )
    op.alter_column(
        "video_projects",
        "current_code_version_id",
        new_column_name="current_script_version_id",
    )

    op.execute("DROP INDEX IF EXISTS idx_code_versions_project_id")
    op.rename_table("code_versions", "script_versions")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_script_versions_project_id "
        "ON script_versions (project_id)"
    )
