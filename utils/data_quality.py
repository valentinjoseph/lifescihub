"""Data quality validation helpers for local pipeline runs."""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.scraper import RESULT_COLUMNS


def validate_scraped_data(records: list[dict[str, Any]] | pd.DataFrame, min_title_length: int = 10) -> pd.DataFrame:
    """Validate, normalize, and deduplicate scraped article records."""
    df = records.copy() if isinstance(records, pd.DataFrame) else pd.DataFrame.from_records(records, columns=RESULT_COLUMNS)
    if df.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    df = df.copy()
    df["url"] = df["url"].fillna("").astype(str).str.strip()
    df["title"] = df["title"].fillna("").astype(str).str.strip()

    df = df[df["url"].str.match(r"^https?://", na=False)]
    df = df[df["title"].str.len() >= int(min_title_length)]
    df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)
    return df


def aggregate_metrics(df: pd.DataFrame, scrape_metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Combine scrape-layer metrics with validation-layer metrics."""
    scrape_metrics = dict(scrape_metrics or {})
    metrics = {
        "urls_attempted": int(scrape_metrics.get("urls_attempted", 0)),
        "urls_fetched": int(scrape_metrics.get("urls_fetched", 0)),
        "parse_success_count": int(scrape_metrics.get("parse_success_count", 0)),
        "avg_response_time_ms": float(scrape_metrics.get("avg_response_time_ms", 0.0)),
        "error_count": int(scrape_metrics.get("error_count", 0)),
        "unique_urls": 0,
    }

    if df.empty:
        return metrics

    metrics["unique_urls"] = int(df["url"].nunique())
    metrics["parse_success_count"] = int(df["title"].notna().sum())
    if not scrape_metrics.get("avg_response_time_ms") and "response_time_ms" in df:
        metrics["avg_response_time_ms"] = float(df["response_time_ms"].dropna().mean())
    return metrics
