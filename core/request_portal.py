"""Helpers for guest/admin company source requests."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import text

from db.session import engine

FLOW_NAME = "GTM_SOURCE_SCRAPING"
DEFAULT_INDUSTRY_SECTOR = "LIFESCIENCE"
INDUSTRY_SECTORS = [
    "LIFESCIENCE",
    "BANKING",
    "TELECOMMUNICATION",
    "ENERGY",
    "DEFENSE",
    "AIR",
    "SPACE",
    "TRANSPORT",
]
REQUEST_STATUS_PENDING = "PENDING"
REQUEST_STATUS_APPROVED = "APPROVED"
REQUEST_STATUS_REJECTED = "REJECTED"


def normalize_industry_sector(value: str | None) -> str:
    sector = (value or DEFAULT_INDUSTRY_SECTOR).strip().upper()
    if sector not in INDUSTRY_SECTORS:
        raise ValueError("Invalid industry sector")
    return sector


def ensure_request_tables() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE SCHEMA IF NOT EXISTS tech;

                CREATE TABLE IF NOT EXISTS tech.tech_company_requests (
                    request_id TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    requested_industry_sector TEXT NOT NULL DEFAULT 'LIFESCIENCE',
                    source_url TEXT NOT NULL,
                    submitter_username TEXT NOT NULL,
                    submitter_role TEXT NOT NULL,
                    review_status TEXT NOT NULL DEFAULT 'PENDING',
                    reviewer_username TEXT,
                    review_note TEXT,
                    requested_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
                    reviewed_ts TIMESTAMPTZ
                );
                """
            )
        )
        connection.execute(
            text(
                """
                ALTER TABLE tech.tech_company_requests
                ADD COLUMN IF NOT EXISTS requested_industry_sector TEXT NOT NULL DEFAULT 'LIFESCIENCE'
                """
            )
        )


def list_company_requests(role: str, username: str) -> list[dict[str, Any]]:
    ensure_request_tables()
    query = """
        SELECT
            request_id,
            company_name,
            requested_industry_sector,
            source_url,
            submitter_username,
            submitter_role,
            review_status,
            reviewer_username,
            review_note,
            requested_ts,
            reviewed_ts
        FROM tech.tech_company_requests
    """
    params: dict[str, Any] = {}
    if role != "admin":
        query += " WHERE submitter_username = :submitter_username"
        params["submitter_username"] = username
    query += " ORDER BY requested_ts DESC"

    with engine.begin() as connection:
        rows = connection.execute(text(query), params).mappings().all()
    return [dict(row) for row in rows]


def create_company_request(
    company_name: str,
    industry_sector: str,
    source_url: str,
    submitter_username: str,
    submitter_role: str,
) -> str:
    ensure_request_tables()
    request_id = str(uuid4())
    requested_industry_sector = normalize_industry_sector(industry_sector)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO tech.tech_company_requests (
                    request_id,
                    company_name,
                    requested_industry_sector,
                    source_url,
                    submitter_username,
                    submitter_role,
                    review_status
                ) VALUES (
                    :request_id,
                    :company_name,
                    :requested_industry_sector,
                    :source_url,
                    :submitter_username,
                    :submitter_role,
                    :review_status
                )
                """
            ),
            {
                "request_id": request_id,
                "company_name": company_name,
                "requested_industry_sector": requested_industry_sector,
                "source_url": source_url,
                "submitter_username": submitter_username,
                "submitter_role": submitter_role,
                "review_status": REQUEST_STATUS_PENDING,
            },
        )
    return request_id


def review_company_request(
    request_id: str,
    reviewer_username: str,
    approved: bool,
    review_note: str | None = None,
    industry_sector: str | None = None,
) -> None:
    ensure_request_tables()
    with engine.begin() as connection:
        request_row = connection.execute(
            text(
                """
                SELECT request_id, company_name, requested_industry_sector, source_url, review_status
                FROM tech.tech_company_requests
                WHERE request_id = :request_id
                """
            ),
            {"request_id": request_id},
        ).mappings().one_or_none()
        if request_row is None:
            raise ValueError("Request not found")
        if request_row["review_status"] != REQUEST_STATUS_PENDING:
            raise ValueError("Request has already been reviewed")

        if approved:
            approved_industry_sector = normalize_industry_sector(
                industry_sector or str(request_row["requested_industry_sector"])
            )
            _apply_company_request(
                connection,
                str(request_row["company_name"]),
                approved_industry_sector,
                str(request_row["source_url"]),
            )
            new_status = REQUEST_STATUS_APPROVED
        else:
            new_status = REQUEST_STATUS_REJECTED

        connection.execute(
            text(
                """
                UPDATE tech.tech_company_requests
                SET review_status = :review_status,
                    requested_industry_sector = :requested_industry_sector,
                    reviewer_username = :reviewer_username,
                    review_note = :review_note,
                    reviewed_ts = now()
                WHERE request_id = :request_id
                """
            ),
            {
                "request_id": request_id,
                "review_status": new_status,
                "requested_industry_sector": (
                    normalize_industry_sector(industry_sector)
                    if industry_sector
                    else str(request_row["requested_industry_sector"])
                ),
                "reviewer_username": reviewer_username,
                "review_note": review_note or None,
            },
        )


def _apply_company_request(connection, company_name: str, industry_sector: str, source_url: str) -> None:
    connection.execute(
        text("ALTER TABLE tech.tech_load_sources ADD COLUMN IF NOT EXISTS industry_sector TEXT NOT NULL DEFAULT 'LIFESCIENCE'")
    )
    connection.execute(
        text("ALTER TABLE tech.tech_load_config ADD COLUMN IF NOT EXISTS industry_sector TEXT NOT NULL DEFAULT 'LIFESCIENCE'")
    )
    existing_config = connection.execute(
        text(
            """
            SELECT load_type, active_flag, industry_sector
            FROM tech.tech_load_config
            WHERE flow_name = :flow_name AND company_name = :company_name
            """
        ),
        {"flow_name": FLOW_NAME, "company_name": company_name},
    ).mappings().one_or_none()
    load_type = str(existing_config["load_type"]).strip() if existing_config and existing_config["load_type"] else "FULL"
    industry_sector = normalize_industry_sector(industry_sector)

    existing_sources = connection.execute(
        text(
            """
            SELECT source_1, source_2, source_3, source_4, source_5
            FROM tech.tech_load_sources
            WHERE company_name = :company_name
            """
        ),
        {"company_name": company_name},
    ).mappings().one_or_none()
    if existing_sources:
        ordered_sources = [existing_sources.get(f"source_{index}") for index in range(1, 6)]
        normalized_sources = [str(value).strip() for value in ordered_sources if value]
        if source_url not in normalized_sources:
            if len(normalized_sources) >= 5:
                raise ValueError("Company already has five configured sources")
            normalized_sources.append(source_url)
        source_values = normalized_sources + [None] * (5 - len(normalized_sources))
    else:
        source_values = [source_url, None, None, None, None]

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
        {
            "company_name": company_name,
            "industry_sector": industry_sector,
            "source_1": source_values[0],
            "source_2": source_values[1],
            "source_3": source_values[2],
            "source_4": source_values[3],
            "source_5": source_values[4],
        },
    )

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
        {
            "flow_name": FLOW_NAME,
            "company_name": company_name,
            "load_type": load_type or "FULL",
            "active_flag": "Y",
            "industry_sector": industry_sector,
        },
    )
