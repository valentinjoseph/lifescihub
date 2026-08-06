"""rename tech table prefix from ls to tech

Revision ID: 0006_rename_tech_tables_prefix
Revises: 0005_sector_staging
Create Date: 2026-08-06 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0006_rename_tech_tables_prefix"
down_revision: Union[str, Sequence[str], None] = "0005_sector_staging"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_RENAMES = {
    "ls_load_sources": "tech_load_sources",
    "ls_load_config": "tech_load_config",
    "ls_scraping_config": "tech_scraping_config",
    "ls_load_monitoring": "tech_load_monitoring",
    "ls_article_summary": "tech_article_summary",
    "ls_title_exclusion": "tech_title_exclusion",
    "ls_company_requests": "tech_company_requests",
    "ls_hub_activity_monitoring": "tech_hub_activity_monitoring",
}


def _rename_tables(mapping: dict[str, str]) -> None:
    bind = op.get_bind()
    for source, target in mapping.items():
        bind.exec_driver_sql(
            f"""
            DO $$
            BEGIN
                IF to_regclass('tech.{source}') IS NOT NULL
                   AND to_regclass('tech.{target}') IS NULL THEN
                    ALTER TABLE tech.{source} RENAME TO {target};
                END IF;
            END $$;
            """
        )


def upgrade() -> None:
    _rename_tables(TABLE_RENAMES)
    bind = op.get_bind()
    bind.exec_driver_sql("ALTER INDEX IF EXISTS tech.ls_load_config_pk RENAME TO tech_load_config_pk")
    bind.exec_driver_sql("ALTER INDEX IF EXISTS tech.idx_ls_title_exclusion_id RENAME TO idx_tech_title_exclusion_id")
    bind.exec_driver_sql("ALTER INDEX IF EXISTS tech.idx_ls_title_exclusion_company RENAME TO idx_tech_title_exclusion_company")


def downgrade() -> None:
    _rename_tables({target: source for source, target in TABLE_RENAMES.items()})
    bind = op.get_bind()
    bind.exec_driver_sql("ALTER INDEX IF EXISTS tech.tech_load_config_pk RENAME TO ls_load_config_pk")
    bind.exec_driver_sql("ALTER INDEX IF EXISTS tech.idx_tech_title_exclusion_id RENAME TO idx_ls_title_exclusion_id")
    bind.exec_driver_sql("ALTER INDEX IF EXISTS tech.idx_tech_title_exclusion_company RENAME TO idx_ls_title_exclusion_company")
