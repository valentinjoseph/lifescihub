"""create tech schema

Revision ID: 0001_create_tech_schema
Revises:
Create Date: 2026-04-17 19:05:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0001_create_tech_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS tech")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS tech CASCADE")
