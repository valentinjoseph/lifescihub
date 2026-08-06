"""add industry sector and sector staging schemas

Revision ID: 0005_sector_staging
Revises: 0004_structured_summary
Create Date: 2026-08-05 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0005_sector_staging"
down_revision: Union[str, Sequence[str], None] = "0004_structured_summary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            load_sources_table TEXT := CASE
                WHEN to_regclass('tech.tech_load_sources') IS NOT NULL THEN 'tech.tech_load_sources'
                ELSE 'tech.ls_load_sources'
            END;
            load_config_table TEXT := CASE
                WHEN to_regclass('tech.tech_load_config') IS NOT NULL THEN 'tech.tech_load_config'
                ELSE 'tech.ls_load_config'
            END;
        BEGIN
            IF to_regclass(load_sources_table) IS NOT NULL THEN
                EXECUTE format('ALTER TABLE %s ADD COLUMN IF NOT EXISTS industry_sector TEXT NOT NULL DEFAULT %L', load_sources_table, 'LIFESCIENCE');
                EXECUTE format('UPDATE %s SET industry_sector = %L WHERE industry_sector IS NULL OR btrim(industry_sector) = %L', load_sources_table, 'LIFESCIENCE', '');
            END IF;

            IF to_regclass(load_config_table) IS NOT NULL THEN
                EXECUTE format('ALTER TABLE %s ADD COLUMN IF NOT EXISTS industry_sector TEXT NOT NULL DEFAULT %L', load_config_table, 'LIFESCIENCE');
                EXECUTE format('UPDATE %s SET industry_sector = %L WHERE industry_sector IS NULL OR btrim(industry_sector) = %L', load_config_table, 'LIFESCIENCE', '');
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            staging_table RECORD;
            company_slug TEXT;
            target_table TEXT;
        BEGIN
            CREATE SCHEMA IF NOT EXISTS stg_lifescience;

            FOR staging_table IN
                SELECT schemaname, tablename
                FROM pg_tables
                WHERE schemaname LIKE 'stg_ls_%'
                  AND tablename LIKE 'stg_%'
                ORDER BY schemaname, tablename
            LOOP
                company_slug := regexp_replace(staging_table.schemaname, '^stg_ls_', '');
                target_table := 'stg_' || company_slug;
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS stg_lifescience.%I (
                        id TEXT,
                        url TEXT PRIMARY KEY,
                        title TEXT,
                        article_content TEXT,
                        published_date TIMESTAMPTZ,
                        s_created_ts TIMESTAMPTZ
                    )',
                    target_table
                );

                EXECUTE format(
                    'INSERT INTO stg_lifescience.%I (
                        id, url, title, article_content, published_date, s_created_ts
                    )
                    SELECT id, url, title, article_content, published_date, s_created_ts
                    FROM %I.%I
                    ON CONFLICT (url) DO NOTHING',
                    target_table,
                    staging_table.schemaname,
                    staging_table.tablename
                );
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('tech.tech_load_config') IS NOT NULL THEN
                ALTER TABLE tech.tech_load_config DROP COLUMN IF EXISTS industry_sector;
            ELSIF to_regclass('tech.ls_load_config') IS NOT NULL THEN
                ALTER TABLE tech.ls_load_config DROP COLUMN IF EXISTS industry_sector;
            END IF;

            IF to_regclass('tech.tech_load_sources') IS NOT NULL THEN
                ALTER TABLE tech.tech_load_sources DROP COLUMN IF EXISTS industry_sector;
            ELSIF to_regclass('tech.ls_load_sources') IS NOT NULL THEN
                ALTER TABLE tech.ls_load_sources DROP COLUMN IF EXISTS industry_sector;
            END IF;
        END $$;
        """
    )
