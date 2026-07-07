"""split ai provider models

Revision ID: 91c3f0a8d2b4
Revises: 5f4a2e8c9d10
"""

from typing import Sequence, Union

from alembic import op


revision: str = "91c3f0a8d2b4"
down_revision: Union[str, Sequence[str], None] = "5f4a2e8c9d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration is intentionally defensive because 5f4a2e8c9d10 briefly
    # existed locally as a one-level provider+model table before being split.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_provider_models (
            id UUID PRIMARY KEY,
            provider_id UUID NOT NULL,
            name VARCHAR(100) NOT NULL,
            model VARCHAR(150) NOT NULL,
            content_max_tokens INTEGER NOT NULL,
            json_max_tokens INTEGER NOT NULL,
            input_cost_per_million NUMERIC(18, 8) NOT NULL,
            cached_input_cost_per_million NUMERIC(18, 8) NOT NULL,
            output_cost_per_million NUMERIC(18, 8) NOT NULL,
            is_active BOOLEAN NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_provider_models_provider_id "
        "ON ai_provider_models (provider_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_provider_models_model "
        "ON ai_provider_models (model)"
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ai_model_providers' AND column_name = 'model'
            ) THEN
                EXECUTE $sql$
                    INSERT INTO ai_provider_models (
                        id,
                        provider_id,
                        name,
                        model,
                        content_max_tokens,
                        json_max_tokens,
                        input_cost_per_million,
                        cached_input_cost_per_million,
                        output_cost_per_million,
                        is_active,
                        created_at,
                        updated_at
                    )
                    SELECT
                        p.id,
                        p.id,
                        COALESCE(NULLIF(p.model, ''), p.name),
                        p.model,
                        p.content_max_tokens,
                        p.json_max_tokens,
                        p.input_cost_per_million,
                        p.cached_input_cost_per_million,
                        p.output_cost_per_million,
                        p.is_active,
                        p.created_at,
                        p.updated_at
                    FROM ai_model_providers p
                    WHERE p.model IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM ai_provider_models m
                        WHERE m.provider_id = p.id AND m.model = p.model
                      )
                $sql$;
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ai_business_model_configs'
                  AND column_name = 'model_id'
            ) THEN
                ALTER TABLE ai_business_model_configs ADD COLUMN model_id UUID;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ai_business_model_configs'
                  AND column_name = 'provider_id'
            ) THEN
                UPDATE ai_business_model_configs c
                SET model_id = picked.model_id
                FROM (
                    SELECT DISTINCT ON (provider_id)
                        provider_id,
                        id AS model_id
                    FROM ai_provider_models
                    ORDER BY provider_id, created_at DESC
                ) picked
                WHERE c.model_id IS NULL
                  AND c.provider_id = picked.provider_id;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM ai_business_model_configs WHERE model_id IS NULL
            ) THEN
                ALTER TABLE ai_business_model_configs ALTER COLUMN model_id SET NOT NULL;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ai_business_model_configs'
                  AND column_name = 'provider_id'
            ) THEN
                UPDATE ai_business_model_configs c
                SET provider_id = m.provider_id
                FROM ai_provider_models m
                WHERE c.model_id = m.id
                  AND c.provider_id IS NULL;
            END IF;
        END $$;
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_ai_provider_models_model")
    op.execute("DROP INDEX IF EXISTS ix_ai_provider_models_provider_id")
    op.execute("DROP TABLE IF EXISTS ai_provider_models")
