"""Bootstrap PostgreSQL tables from existing local seed files."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db.session import engine
from db.table_manager import PostgresTableManager, get_target_schema_and_table


def ensure_core_tables() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE SCHEMA IF NOT EXISTS tech;

                CREATE TABLE IF NOT EXISTS tech.tech_load_sources (
                    company_name TEXT PRIMARY KEY,
                    industry_sector TEXT NOT NULL DEFAULT 'LIFESCIENCE',
                    source_1 TEXT,
                    source_2 TEXT,
                    source_3 TEXT,
                    source_4 TEXT,
                    source_5 TEXT,
                    s_created_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
                    s_modified_ts TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE TABLE IF NOT EXISTS tech.tech_load_config (
                    flow_name TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    load_type TEXT,
                    active_flag TEXT,
                    industry_sector TEXT NOT NULL DEFAULT 'LIFESCIENCE',
                    selectors TEXT[],
                    s_created_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
                    s_modified_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT tech_load_config_pk PRIMARY KEY (flow_name, company_name)
                );

                CREATE TABLE IF NOT EXISTS tech.tech_scraping_config (
                    param_name TEXT PRIMARY KEY,
                    param_value TEXT NOT NULL,
                    description TEXT,
                    s_created_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
                    s_modified_ts TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE TABLE IF NOT EXISTS tech.tech_load_monitoring (
                    run_id TEXT NOT NULL,
                    run_name TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    target_schema TEXT NOT NULL,
                    target_table TEXT NOT NULL,
                    load_type TEXT NOT NULL,
                    run_status TEXT NOT NULL,
                    run_message TEXT,
                    records_inserted BIGINT NOT NULL DEFAULT 0,
                    urls_attempted BIGINT NOT NULL DEFAULT 0,
                    urls_fetched BIGINT NOT NULL DEFAULT 0,
                    parse_success_count BIGINT NOT NULL DEFAULT 0,
                    avg_response_time_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
                    error_count BIGINT NOT NULL DEFAULT 0,
                    run_start_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
                    run_end_ts TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
        )
        connection.execute(
            text("ALTER TABLE tech.tech_load_sources ADD COLUMN IF NOT EXISTS industry_sector TEXT NOT NULL DEFAULT 'LIFESCIENCE'")
        )
        connection.execute(
            text(
                """
                UPDATE tech.tech_load_sources
                SET industry_sector = 'LIFESCIENCE'
                WHERE industry_sector IS NULL OR btrim(industry_sector) = ''
                """
            )
        )
        connection.execute(
            text("ALTER TABLE tech.tech_load_config ADD COLUMN IF NOT EXISTS industry_sector TEXT NOT NULL DEFAULT 'LIFESCIENCE'")
        )
        connection.execute(
            text(
                """
                UPDATE tech.tech_load_config
                SET industry_sector = 'LIFESCIENCE'
                WHERE industry_sector IS NULL OR btrim(industry_sector) = ''
                """
            )
        )


def _table_has_rows(table_name: str) -> bool:
    with engine.begin() as connection:
        count = connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
    return bool(count)


def seed_sources_from_csv(path: Path) -> None:
    if not path.exists() or _table_has_rows("tech.tech_load_sources"):
        return

    df = pd.read_csv(path).fillna("")
    rows = [
        {
            "company_name": str(row.get("COMPANY_NAME", "")).strip(),
            "industry_sector": str(row.get("INDUSTRY_SECTOR", "LIFESCIENCE")).strip().upper() or "LIFESCIENCE",
            "source_1": str(row.get("SOURCE_1", "")).strip() or None,
            "source_2": str(row.get("SOURCE_2", "")).strip() or None,
            "source_3": str(row.get("SOURCE_3", "")).strip() or None,
            "source_4": str(row.get("SOURCE_4", "")).strip() or None,
            "source_5": str(row.get("SOURCE_5", "")).strip() or None,
        }
        for _, row in df.iterrows()
        if str(row.get("COMPANY_NAME", "")).strip()
    ]
    if not rows:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO tech.tech_load_sources (
                    company_name, industry_sector, source_1, source_2, source_3, source_4, source_5
                ) VALUES (
                    :company_name, :industry_sector, :source_1, :source_2, :source_3, :source_4, :source_5
                )
                ON CONFLICT (company_name) DO UPDATE SET
                    industry_sector = EXCLUDED.industry_sector,
                    source_1 = EXCLUDED.source_1,
                    source_2 = EXCLUDED.source_2,
                    source_3 = EXCLUDED.source_3,
                    source_4 = EXCLUDED.source_4,
                    source_5 = EXCLUDED.source_5,
                    s_modified_ts = now()
                """
            ),
            rows,
        )


def seed_load_config_from_csv(path: Path) -> None:
    if not path.exists() or _table_has_rows("tech.tech_load_config"):
        return

    df = pd.read_csv(path).fillna("")
    rows = [
        {
            "flow_name": str(row.get("FLOW_NAME", "")).strip(),
            "company_name": str(row.get("COMPANY_NAME", "")).strip(),
            "load_type": str(row.get("LOAD_TYPE", "")).strip() or None,
            "active_flag": str(row.get("ACTIVE_FLAG", "")).strip() or None,
            "industry_sector": str(row.get("INDUSTRY_SECTOR", "LIFESCIENCE")).strip().upper() or "LIFESCIENCE",
        }
        for _, row in df.iterrows()
        if str(row.get("FLOW_NAME", "")).strip() and str(row.get("COMPANY_NAME", "")).strip()
    ]
    if not rows:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO tech.tech_load_config (
                    flow_name, company_name, load_type, active_flag, industry_sector
                ) VALUES (
                    :flow_name, :company_name, :load_type, :active_flag, :industry_sector
                )
                ON CONFLICT (flow_name, company_name) DO UPDATE SET
                    load_type = EXCLUDED.load_type,
                    active_flag = EXCLUDED.active_flag,
                    industry_sector = EXCLUDED.industry_sector,
                    s_modified_ts = now()
                """
            ),
            rows,
        )


def seed_scraping_config_from_json(path: Path) -> None:
    if not path.exists() or _table_has_rows("tech.tech_scraping_config"):
        return

    payload = json.loads(path.read_text(encoding="utf-8"))
    descriptions = {
        "MAX_ITEMS_PER_SOURCE": "Maximum articles to fetch per source",
        "MAX_WORKERS": "Maximum worker threads for scraping",
        "LISTING_SLEEP_SEC": "Delay between listing page requests",
        "ARTICLE_SLEEP_SEC": "Delay between article requests",
        "REQUEST_TIMEOUT_SEC": "Per-request timeout in seconds",
        "MIN_TITLE_LENGTH": "Minimum accepted article title length",
        "EXPORT_RESULTS": "Whether to export the latest validated CSV",
    }
    rows = [
        {
            "param_name": key,
            "param_value": json.dumps(value) if isinstance(value, bool) else str(value),
            "description": descriptions.get(key),
        }
        for key, value in payload.items()
    ]

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO tech.tech_scraping_config (param_name, param_value, description)
                VALUES (:param_name, :param_value, :description)
                ON CONFLICT (param_name) DO UPDATE SET
                    param_value = EXCLUDED.param_value,
                    description = EXCLUDED.description,
                    s_modified_ts = now()
                """
            ),
            rows,
        )


def import_legacy_sqlite(sqlite_path: Path) -> None:
    if not sqlite_path.exists():
        return

    manager = PostgresTableManager()
    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        table_rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()

        for row in table_rows:
            table_name = row["name"]
            if table_name == "load_monitoring":
                if _table_has_rows("tech.tech_load_monitoring"):
                    continue
                monitoring_rows = [
                    dict(item)
                    for item in connection.execute("SELECT * FROM load_monitoring").fetchall()
                ]
                if monitoring_rows:
                    with engine.begin() as pg_connection:
                        pg_connection.execute(
                            text(
                                """
                                INSERT INTO tech.tech_load_monitoring (
                                    run_id, run_name, company_name, target_schema, target_table, load_type,
                                    run_status, run_message, records_inserted, urls_attempted, urls_fetched,
                                    parse_success_count, avg_response_time_ms, error_count, run_start_ts, run_end_ts
                                ) VALUES (
                                    :run_id, :run_name, :company_name, :target_schema, :target_table, :load_type,
                                    :run_status, :run_message, :records_inserted, :urls_attempted, :urls_fetched,
                                    :parse_success_count, :avg_response_time_ms, :error_count, :run_start_ts, :run_end_ts
                                )
                                ON CONFLICT DO NOTHING
                                """
                            ),
                            monitoring_rows,
                        )
                continue

            if "__" not in table_name:
                continue

            schema_name, postgres_table = table_name.split("__", 1)
            rows = [dict(item) for item in connection.execute(f'SELECT * FROM "{table_name}"').fetchall()]
            if not rows:
                continue
            company_name = schema_name.removeprefix("stg_ls_").replace("_", " ")
            target_schema, target_table = get_target_schema_and_table(company_name)
            manager.ensure_company_table("local", target_schema, target_table)
            manager.insert_rows(target_schema, target_table, rows)


def bootstrap_postgres(
    sources_path: Path,
    load_config_path: Path,
    scraping_config_path: Path,
    sqlite_path: Path,
) -> None:
    ensure_core_tables()
    seed_sources_from_csv(sources_path)
    seed_load_config_from_csv(load_config_path)
    seed_scraping_config_from_json(scraping_config_path)
    import_legacy_sqlite(sqlite_path)
