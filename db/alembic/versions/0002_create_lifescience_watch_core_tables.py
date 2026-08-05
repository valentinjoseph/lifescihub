"""create lifescience watch core tables

Revision ID: 0002_create_lsw_core_tables
Revises: 0001_create_tech_schema
Create Date: 2026-04-18 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_create_lsw_core_tables"
down_revision: Union[str, Sequence[str], None] = "0001_create_tech_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ls_load_sources",
        sa.Column("company_name", sa.Text(), primary_key=True, nullable=False),
        sa.Column("industry_sector", sa.Text(), nullable=False, server_default="LIFESCIENCE"),
        sa.Column("source_1", sa.Text(), nullable=True),
        sa.Column("source_2", sa.Text(), nullable=True),
        sa.Column("source_3", sa.Text(), nullable=True),
        sa.Column("source_4", sa.Text(), nullable=True),
        sa.Column("source_5", sa.Text(), nullable=True),
        sa.Column("s_created_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("s_modified_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="tech",
    )

    op.create_table(
        "ls_load_config",
        sa.Column("flow_name", sa.Text(), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("load_type", sa.Text(), nullable=True),
        sa.Column("active_flag", sa.Text(), nullable=True),
        sa.Column("selectors", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("s_created_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("s_modified_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("flow_name", "company_name", name="ls_load_config_pk"),
        schema="tech",
    )

    op.create_table(
        "ls_scraping_config",
        sa.Column("param_name", sa.Text(), primary_key=True, nullable=False),
        sa.Column("param_value", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("s_created_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("s_modified_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="tech",
    )

    op.create_table(
        "ls_load_monitoring",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("run_name", sa.Text(), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("target_schema", sa.Text(), nullable=False),
        sa.Column("target_table", sa.Text(), nullable=False),
        sa.Column("load_type", sa.Text(), nullable=False),
        sa.Column("run_status", sa.Text(), nullable=False),
        sa.Column("run_message", sa.Text(), nullable=True),
        sa.Column("records_inserted", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("urls_attempted", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("urls_fetched", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("parse_success_count", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_response_time_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_count", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("run_start_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("run_end_ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="tech",
    )


def downgrade() -> None:
    op.drop_table("ls_load_monitoring", schema="tech")
    op.drop_table("ls_scraping_config", schema="tech")
    op.drop_table("ls_load_config", schema="tech")
    op.drop_table("ls_load_sources", schema="tech")
