"""Monitoring and metrics tracking backed by PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import text

from db.session import engine


class ScrapingMonitor:
    """Manage monitoring and run history for local pipeline runs."""

    def __init__(self, flow_name: str, run_id: str):
        self.flow_name = flow_name
        self.run_id = run_id
        self._initialize_monitoring_table()

    def _initialize_monitoring_table(self) -> None:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS tech.ls_load_monitoring (
                    run_id TEXT,
                    run_name TEXT,
                    company_name TEXT,
                    target_schema TEXT,
                    target_table TEXT,
                    load_type TEXT,
                    run_status TEXT,
                    run_message TEXT,
                    records_inserted INTEGER,
                    urls_attempted INTEGER,
                    urls_fetched INTEGER,
                    parse_success_count INTEGER,
                    avg_response_time_ms REAL,
                    error_count INTEGER,
                    run_start_ts TIMESTAMPTZ,
                    run_end_ts TIMESTAMPTZ
                )
                """
                )
            )

    def log_completion(
        self,
        company_name: str,
        target_schema: str,
        target_table: str,
        load_type: str,
        status: str,
        message: str,
        records_inserted: int,
        metrics: Optional[dict] = None,
    ) -> None:
        metrics = metrics or {}
        timestamp = datetime.now(UTC).isoformat()
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                INSERT INTO tech.ls_load_monitoring (
                    run_id, run_name, company_name, target_schema, target_table, load_type,
                    run_status, run_message, records_inserted, urls_attempted, urls_fetched,
                    parse_success_count, avg_response_time_ms, error_count, run_start_ts, run_end_ts
                ) VALUES (
                    :run_id, :run_name, :company_name, :target_schema, :target_table, :load_type,
                    :run_status, :run_message, :records_inserted, :urls_attempted, :urls_fetched,
                    :parse_success_count, :avg_response_time_ms, :error_count, :run_start_ts, :run_end_ts
                )
                """,
                ),
                {
                    "run_id": self.run_id,
                    "run_name": self.flow_name,
                    "company_name": company_name,
                    "target_schema": target_schema,
                    "target_table": target_table,
                    "load_type": load_type,
                    "run_status": status,
                    "run_message": message,
                    "records_inserted": int(records_inserted),
                    "urls_attempted": int(metrics.get("urls_attempted", 0)),
                    "urls_fetched": int(metrics.get("urls_fetched", 0)),
                    "parse_success_count": int(metrics.get("parse_success_count", 0)),
                    "avg_response_time_ms": float(metrics.get("avg_response_time_ms", 0.0)),
                    "error_count": int(metrics.get("error_count", 0)),
                    "run_start_ts": timestamp,
                    "run_end_ts": timestamp,
                },
            )

    def get_last_success_timestamp(self, company_name: str) -> Optional[datetime]:
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                SELECT MAX(run_end_ts) AS last_success
                FROM tech.ls_load_monitoring
                WHERE run_name = :run_name AND company_name = :company_name AND run_status = 'SUCCESS'
                """,
                ),
                {"run_name": self.flow_name, "company_name": company_name},
            ).mappings().one()

        if not row["last_success"]:
            return None
        return row["last_success"]
