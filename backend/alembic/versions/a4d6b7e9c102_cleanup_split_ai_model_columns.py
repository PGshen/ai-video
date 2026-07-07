"""cleanup split ai model columns

Revision ID: a4d6b7e9c102
Revises: 91c3f0a8d2b4
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a4d6b7e9c102"
down_revision: Union[str, Sequence[str], None] = "91c3f0a8d2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Old local copies of 5f4a2e8c9d10 created provider rows with model fields
    # directly on ai_model_providers. The application now stores those fields in
    # ai_provider_models, so remove the stale NOT NULL columns after the split.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ai_model_providers' AND column_name = 'model'
            ) THEN
                ALTER TABLE ai_model_providers DROP COLUMN model;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ai_model_providers' AND column_name = 'content_max_tokens'
            ) THEN
                ALTER TABLE ai_model_providers DROP COLUMN content_max_tokens;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ai_model_providers' AND column_name = 'json_max_tokens'
            ) THEN
                ALTER TABLE ai_model_providers DROP COLUMN json_max_tokens;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ai_model_providers' AND column_name = 'input_cost_per_million'
            ) THEN
                ALTER TABLE ai_model_providers DROP COLUMN input_cost_per_million;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ai_model_providers' AND column_name = 'cached_input_cost_per_million'
            ) THEN
                ALTER TABLE ai_model_providers DROP COLUMN cached_input_cost_per_million;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ai_model_providers' AND column_name = 'output_cost_per_million'
            ) THEN
                ALTER TABLE ai_model_providers DROP COLUMN output_cost_per_million;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ai_business_model_configs' AND column_name = 'provider_id'
            ) THEN
                ALTER TABLE ai_business_model_configs DROP COLUMN provider_id;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # This is a cleanup-only compatibility migration for local pre-split schemas.
    # Re-adding the removed columns would reintroduce the invalid one-level shape,
    # so downgrade is intentionally a no-op.
    pass
