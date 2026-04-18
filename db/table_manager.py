"""PostgreSQL-backed table management for local pipeline runs."""

from __future__ import annotations

import re
from typing import Tuple

import pandas as pd
from sqlalchemy import text

from db.session import engine


def normalize_identifier(name: str) -> str:
    """Normalize a string to a safe SQL identifier."""
    value = name.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    if not value or not value[0].isalpha():
        value = f"x_{value}"
    return value[:128]


def get_target_schema_and_table(company_name: str) -> Tuple[str, str]:
    """Map a company name to its logical schema and table names."""
    base = normalize_identifier(company_name)
    return f"stg_ls_{base}", f"stg_{base}_ingest"


class PostgresTableManager:
    """Create and merge target tables in PostgreSQL."""

    def ensure_company_table(self, catalog: str, schema: str, table: str) -> str:
        del catalog
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            connection.execute(
                text(
                    f'''
                    CREATE TABLE IF NOT EXISTS "{schema}"."{table}" (
                        id TEXT,
                        url TEXT PRIMARY KEY,
                        title TEXT,
                        article_content TEXT,
                        published_date TIMESTAMPTZ,
                        s_created_ts TIMESTAMPTZ
                    )
                    '''
                )
            )
        return f"{schema}.{table}"

    def insert_rows(self, schema: str, table: str, rows: list[dict]) -> int:
        if not rows:
            return 0
        with engine.begin() as connection:
            before = connection.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')).scalar_one()
            connection.execute(
                text(
                    f'''
                    INSERT INTO "{schema}"."{table}" (
                        id, url, title, article_content, published_date, s_created_ts
                    ) VALUES (
                        :id, :url, :title, :article_content, :published_date, :s_created_ts
                    )
                    ON CONFLICT (url) DO NOTHING
                    '''
                ),
                rows,
            )
            after = connection.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')).scalar_one()
        return int(after - before)

    def merge_company_data(self, schema: str, table: str, source_df: pd.DataFrame) -> int:
        if source_df.empty:
            return 0
        rows = [
            {
                "id": str(row["id"]),
                "url": str(row["url"]),
                "title": row.get("title"),
                "article_content": row.get("article_content"),
                "published_date": row.get("published_date"),
                "s_created_ts": row.get("s_created_ts"),
            }
            for row in source_df.to_dict(orient="records")
        ]
        return self.insert_rows(schema, table, rows)


def ensure_schema_and_table(
    manager: PostgresTableManager,
    catalog: str,
    schema: str,
    table: str,
) -> str:
    return manager.ensure_company_table(catalog, schema, table)


def merge_data(
    manager: PostgresTableManager,
    catalog: str,
    schema: str,
    table: str,
    source_df: pd.DataFrame,
) -> int:
    del catalog
    return manager.merge_company_data(schema, table, source_df)
