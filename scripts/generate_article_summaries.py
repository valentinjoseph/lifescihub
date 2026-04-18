"""Generate and store article summaries for DWH views."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from openai import OpenAI
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.news_catalog import fetch_articles_for_summarization
from db.session import engine


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def fallback_summary(content: str, max_chars: int = 700) -> str:
    clean = normalize_whitespace(content)
    if not clean:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", clean)
    summary = " ".join(parts[:3]).strip()
    if not summary:
        summary = clean[:max_chars]
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."
    return summary


def ai_summary(client: OpenAI, model: str, company_name: str, title: str, content: str) -> str:
    prompt = (
        "Summarize the following life-sciences article for a business watch dashboard. "
        "Write 3-5 concise sentences covering the key announcement, company context, and material business impact. "
        "Do not use bullet points.\n\n"
        f"Company: {company_name}\n"
        f"Title: {title}\n"
        f"Article Content:\n{content[:12000]}"
    )
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    return normalize_whitespace(response.output_text)


def ensure_summary_table() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS tech.ls_article_summary (
                    article_id TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT,
                    article_summary TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    summary_model TEXT NOT NULL,
                    summary_status TEXT NOT NULL,
                    error_message TEXT,
                    summarized_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )


def upsert_summary(row: dict) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO tech.ls_article_summary (
                    article_id, company_name, url, title, article_summary, content_hash,
                    summary_model, summary_status, error_message, summarized_at
                ) VALUES (
                    :article_id, :company_name, :url, :title, :article_summary, :content_hash,
                    :summary_model, :summary_status, :error_message, :summarized_at
                )
                ON CONFLICT (article_id) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    url = EXCLUDED.url,
                    title = EXCLUDED.title,
                    article_summary = EXCLUDED.article_summary,
                    content_hash = EXCLUDED.content_hash,
                    summary_model = EXCLUDED.summary_model,
                    summary_status = EXCLUDED.summary_status,
                    error_message = EXCLUDED.error_message,
                    summarized_at = EXCLUDED.summarized_at
                """
            ),
            row,
        )


def load_existing_summaries() -> dict[str, dict[str, str]]:
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT article_id, content_hash, summary_status, summary_model
                FROM tech.ls_article_summary
                """
            )
        ).mappings().all()
    return {
        row["article_id"]: {
            "content_hash": row["content_hash"],
            "summary_status": row["summary_status"],
            "summary_model": row["summary_model"],
        }
        for row in rows
    }


def run(limit: int | None = None) -> tuple[int, int]:
    ensure_summary_table()
    articles = fetch_articles_for_summarization()
    if limit is not None:
        articles = articles.head(limit)

    existing_summaries = load_existing_summaries()
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    client = OpenAI(api_key=api_key) if api_key else None

    processed = 0
    updated = 0

    for _, item in articles.iterrows():
        article_id = str(item["id"])
        title = normalize_whitespace(str(item.get("title") or ""))
        content = normalize_whitespace(str(item.get("article_content") or ""))
        if not content:
            continue

        digest = content_hash(content)
        existing_summary = existing_summaries.get(article_id)
        should_refresh_with_ai = bool(
            client
            and existing_summary
            and existing_summary["content_hash"] == digest
            and existing_summary["summary_status"] != "ai"
        )

        if existing_summary and existing_summary["content_hash"] == digest and not should_refresh_with_ai:
            continue

        summary_model = "fallback-extractive-v1"
        summary_status = "fallback"
        error_message = None

        try:
            if client:
                summary_text = ai_summary(client, model, str(item["company_name"]), title, content)
                summary_model = model
                summary_status = "ai"
            else:
                summary_text = fallback_summary(content)
        except Exception as exc:
            summary_text = fallback_summary(content)
            summary_status = "fallback"
            error_message = str(exc)

        if not summary_text:
            continue

        upsert_summary(
            {
                "article_id": article_id,
                "company_name": str(item["company_name"]),
                "url": str(item["url"]),
                "title": title or None,
                "article_summary": summary_text,
                "content_hash": digest,
                "summary_model": summary_model,
                "summary_status": summary_status,
                "error_message": error_message,
                "summarized_at": datetime.now(UTC).isoformat(),
            }
        )
        processed += 1
        updated += 1

    return processed, updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate article summaries for DWH views.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for test runs")
    args = parser.parse_args()
    processed, updated = run(limit=args.limit)
    print(f"processed={processed} updated={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
