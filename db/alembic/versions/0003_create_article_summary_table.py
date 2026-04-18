"""create article summary table

Revision ID: 0003_create_article_summary
Revises: 0002_create_lsw_core_tables
Create Date: 2026-04-18 19:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_create_article_summary"
down_revision: Union[str, Sequence[str], None] = "0002_create_lsw_core_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ls_article_summary",
        sa.Column("article_id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("article_summary", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("summary_model", sa.Text(), nullable=False),
        sa.Column("summary_status", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("summarized_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="tech",
    )


def downgrade() -> None:
    op.drop_table("ls_article_summary", schema="tech")
