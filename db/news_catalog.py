"""Helpers for discovering and querying staging news tables."""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text

from db.session import engine


def discover_staging_tables() -> list[dict[str, str]]:
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT schemaname, tablename
                FROM pg_tables
                WHERE schemaname LIKE 'stg_ls_%'
                ORDER BY schemaname, tablename
                """
            )
        ).mappings().all()

    staging_tables: list[dict[str, str]] = []
    for row in rows:
        schema = row["schemaname"]
        table = row["tablename"]
        company = schema.removeprefix("stg_ls_").replace("_", " ").upper()
        staging_tables.append({"schema": schema, "table": table, "company_name": company})
    return staging_tables


def fetch_all_articles() -> pd.DataFrame:
    tables = discover_staging_tables()
    records: list[pd.DataFrame] = []
    with engine.begin() as connection:
        for item in tables:
            query = text(
                f'''
                SELECT
                    :company_name AS company_name,
                    id,
                    url,
                    title,
                    article_content,
                    published_date,
                    s_created_ts
                FROM "{item["schema"]}"."{item["table"]}"
                '''
            )
            frame = pd.read_sql_query(query, connection, params={"company_name": item["company_name"]})
            if not frame.empty:
                records.append(frame)

    if not records:
        return pd.DataFrame(
            columns=["company_name", "id", "url", "title", "article_content", "published_date", "s_created_ts"]
        )

    combined = pd.concat(records, ignore_index=True)
    return combined.drop_duplicates(subset=["id"]).reset_index(drop=True)


def fetch_articles_for_summarization() -> pd.DataFrame:
    df = fetch_all_articles()
    if df.empty:
        return df

    with engine.begin() as connection:
        excluded_ids = {
            row["id"]
            for row in connection.execute(text("SELECT id FROM tech.ls_title_exclusion WHERE id IS NOT NULL")).mappings()
        }

    if excluded_ids:
        df = df[~df["id"].isin(excluded_ids)].reset_index(drop=True)
    return df
