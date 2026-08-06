"""add structured summary fields

Revision ID: 0004_structured_summary
Revises: 0003_create_article_summary
Create Date: 2026-04-18 20:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_structured_summary"
down_revision: Union[str, Sequence[str], None] = "0003_create_article_summary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tech_article_summary", sa.Column("key_topic", sa.Text(), nullable=True), schema="tech")
    op.add_column("tech_article_summary", sa.Column("business_impact", sa.Text(), nullable=True), schema="tech")
    op.add_column("tech_article_summary", sa.Column("geography", sa.Text(), nullable=True), schema="tech")
    op.add_column("tech_article_summary", sa.Column("signal_type", sa.Text(), nullable=True), schema="tech")


def downgrade() -> None:
    op.drop_column("tech_article_summary", "signal_type", schema="tech")
    op.drop_column("tech_article_summary", "geography", schema="tech")
    op.drop_column("tech_article_summary", "business_impact", schema="tech")
    op.drop_column("tech_article_summary", "key_topic", schema="tech")
