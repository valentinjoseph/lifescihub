"""Account activity tracking for dashboard and request portal users."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from db.session import engine

ACTIVITY_LOGIN = "login"
ACTIVITY_NEWS_FILTER = "news_filter"
ACTIVITY_AI_CHAT = "ai_chat"
ACTIVITY_TABLE = "tech.tech_hub_activity_monitoring"


def ensure_activity_table() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE SCHEMA IF NOT EXISTS tech;

                CREATE TABLE IF NOT EXISTS tech.tech_hub_activity_monitoring (
                    activity_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    activity_path TEXT NOT NULL,
                    activity_meta JSONB,
                    request_id TEXT,
                    client_ip TEXT,
                    created_ts TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
        )


def record_activity(
    username: str,
    role: str,
    activity_type: str,
    activity_path: str,
    *,
    activity_meta: dict[str, Any] | None = None,
    request_id: str | None = None,
    client_ip: str | None = None,
) -> None:
    if not username or not role:
        return
    ensure_activity_table()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO tech.tech_hub_activity_monitoring (
                    activity_id,
                    username,
                    role,
                    activity_type,
                    activity_path,
                    activity_meta,
                    request_id,
                    client_ip
                ) VALUES (
                    :activity_id,
                    :username,
                    :role,
                    :activity_type,
                    :activity_path,
                    CAST(:activity_meta AS JSONB),
                    :request_id,
                    :client_ip
                )
                """
            ),
            {
                "activity_id": str(uuid4()),
                "username": username,
                "role": role,
                "activity_type": activity_type,
                "activity_path": activity_path,
                "activity_meta": json.dumps(activity_meta or {}),
                "request_id": request_id,
                "client_ip": client_ip,
            },
        )


def fetch_activity_summary(days: int = 7) -> list[dict[str, Any]]:
    return fetch_activity_summary_filtered(days=days)


def fetch_activity_summary_filtered(
    *,
    days: int = 7,
    username: str = "ALL",
    activity_type: str = "ALL",
) -> list[dict[str, Any]]:
    ensure_activity_table()
    filters = ["created_ts >= now() - make_interval(days => :days)"]
    params: dict[str, Any] = {"days": days}
    if username != "ALL":
        filters.append("username = :username")
        params["username"] = username
    if activity_type != "ALL":
        filters.append("activity_type = :activity_type")
        params["activity_type"] = activity_type
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT
                    username,
                    role,
                    COUNT(*) FILTER (WHERE activity_type = 'login') AS login_count,
                    COUNT(*) FILTER (WHERE activity_type = 'news_filter') AS news_filter_count,
                    COUNT(*) FILTER (WHERE activity_type = 'ai_chat') AS ai_chat_count,
                    MAX(created_ts) AS last_activity_ts
                FROM tech.tech_hub_activity_monitoring
                WHERE """
                + " AND ".join(filters)
                + """
                GROUP BY username, role
                ORDER BY last_activity_ts DESC, username ASC
                """
            ),
            params,
        ).mappings().all()
    return [dict(row) for row in rows]


def fetch_recent_activity(days: int = 7, limit: int = 50) -> list[dict[str, Any]]:
    return fetch_recent_activity_filtered(days=days, limit=limit)


def fetch_recent_activity_filtered(
    *,
    days: int = 7,
    username: str = "ALL",
    activity_type: str = "ALL",
    limit: int = 50,
) -> list[dict[str, Any]]:
    ensure_activity_table()
    filters = ["created_ts >= now() - make_interval(days => :days)"]
    params: dict[str, Any] = {"days": days, "limit": limit}
    if username != "ALL":
        filters.append("username = :username")
        params["username"] = username
    if activity_type != "ALL":
        filters.append("activity_type = :activity_type")
        params["activity_type"] = activity_type
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT
                    username,
                    role,
                    activity_type,
                    activity_path,
                    activity_meta,
                    created_ts
                FROM tech.tech_hub_activity_monitoring
                WHERE """
                + " AND ".join(filters)
                + """
                ORDER BY created_ts DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    payload: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        meta = item.get("activity_meta")
        if isinstance(meta, str):
            try:
                item["activity_meta"] = json.loads(meta)
            except json.JSONDecodeError:
                item["activity_meta"] = {}
        elif meta is None:
            item["activity_meta"] = {}
        payload.append(item)
    return payload


def list_activity_accounts(days: int = 7) -> list[str]:
    ensure_activity_table()
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT DISTINCT username
                FROM tech.tech_hub_activity_monitoring
                WHERE created_ts >= now() - make_interval(days => :days)
                ORDER BY username ASC
                """
            ),
            {"days": days},
        ).scalars().all()
    return [str(row) for row in rows]
