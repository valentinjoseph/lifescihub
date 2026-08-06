"""rename pipeline flow name to GTM Advisor

Revision ID: 0007_rename_pipeline_flow_name
Revises: 0006_rename_tech_tables_prefix
Create Date: 2026-08-06 00:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0007_rename_pipeline_flow_name"
down_revision: Union[str, Sequence[str], None] = "0006_rename_tech_tables_prefix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_FLOW_NAME = "LS_SOURCE_SCRAPING"
NEW_FLOW_NAME = "GTM_SOURCE_SCRAPING"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE tech.tech_load_config
        SET flow_name = '{NEW_FLOW_NAME}'
        WHERE flow_name = '{OLD_FLOW_NAME}'
          AND NOT EXISTS (
              SELECT 1
              FROM tech.tech_load_config AS existing
              WHERE existing.flow_name = '{NEW_FLOW_NAME}'
                AND existing.company_name = tech.tech_load_config.company_name
          )
        """
    )
    op.execute(
        f"""
        UPDATE tech.tech_load_monitoring
        SET run_name = '{NEW_FLOW_NAME}'
        WHERE run_name = '{OLD_FLOW_NAME}'
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE tech.tech_load_config
        SET flow_name = '{OLD_FLOW_NAME}'
        WHERE flow_name = '{NEW_FLOW_NAME}'
          AND NOT EXISTS (
              SELECT 1
              FROM tech.tech_load_config AS existing
              WHERE existing.flow_name = '{OLD_FLOW_NAME}'
                AND existing.company_name = tech.tech_load_config.company_name
          )
        """
    )
    op.execute(
        f"""
        UPDATE tech.tech_load_monitoring
        SET run_name = '{OLD_FLOW_NAME}'
        WHERE run_name = '{NEW_FLOW_NAME}'
        """
    )
