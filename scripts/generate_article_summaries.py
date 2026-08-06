"""Generate and store article summaries for DWH views."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.news_catalog import fetch_articles_for_summarization
from db.session import engine
from core.llm_client import llm_provider, ollama_generate, ollama_summary_model, openai_client, openai_model
from scripts.purge_summarized_article_content import purge_summarized_article_content

SUMMARY_PROMPT_VERSION = "bw-v3"
DEFAULT_SUMMARY_MAX_CONTENT_CHARS = 6000


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def fallback_summary(content: str, max_chars: int = 700) -> str:
    clean = normalize_whitespace(content)
    if not clean:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", clean)
    summary = " ".join(parts[:2]).strip()
    if not summary:
        summary = clean[:max_chars]
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."
    return summary


def classify_topic(text: str) -> str:
    lowered = text.lower()
    rules = [
        ("regulatory", ["approval", "fda", "ema", "authorized", "regulatory", "clearance", "label"]),
        ("clinical", ["trial", "phase", "study", "efficacy", "safety", "patient", "clinical"]),
        ("partnership", ["partnership", "collaboration", "alliance", "license", "agreement"]),
        ("manufacturing", ["manufacturing", "plant", "facility", "production", "capacity", "supply"]),
        ("financial", ["revenue", "earnings", "results", "guidance", "sales", "investor"]),
        ("m&a", ["acquisition", "acquire", "merger", "divest", "spin-off"]),
        ("product", ["launch", "product", "portfolio", "brand", "device"]),
    ]
    for label, keywords in rules:
        if any(keyword in lowered for keyword in keywords):
            return label
    return "corporate"


def infer_geography(text: str) -> str | None:
    candidates = [
        "Global",
        "United States",
        "Europe",
        "France",
        "Germany",
        "United Kingdom",
        "India",
        "China",
        "Japan",
        "Canada",
        "Brazil",
    ]
    lowered = text.lower()
    for candidate in candidates:
        if candidate.lower() in lowered:
            return candidate
    return None


def fallback_structured_summary(company_name: str, title: str, content: str) -> dict[str, str | None]:
    text = normalize_whitespace(f"{company_name}. {title}. {content}")
    return {
        "article_summary": fallback_summary(content),
        "key_topic": classify_topic(text),
        "business_impact": fallback_summary(content, max_chars=260),
        "geography": infer_geography(text),
        "signal_type": classify_topic(text),
    }


def parse_json_object(raw_text: str) -> dict[str, object]:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def summary_prompt(company_name: str, title: str, content: str) -> str:
    max_content_chars = int(os.getenv("SUMMARY_MAX_CONTENT_CHARS", str(DEFAULT_SUMMARY_MAX_CONTENT_CHARS)))
    return (
        "You are writing for a multi-sector business watch spreadsheet used by executives. "
        "Return valid JSON only with keys: article_summary, key_topic, business_impact, geography, signal_type. "
        "article_summary must be 2-4 concise sentences in plain English. Sentence 1 states the key announcement. "
        "Sentence 2 explains why it matters commercially, operationally, clinically, or strategically. "
        "business_impact must be 1 short sentence focused on commercial or strategic relevance. "
        "key_topic must be one of regulatory, clinical, partnership, manufacturing, financial, m&a, product, corporate. "
        "signal_type must be a short business signal label such as approval, trial-readout, partnership, plant-expansion, earnings, leadership-change, launch, acquisition. "
        "geography must be a short region or country string if clear, otherwise null. "
        "Avoid hype, boilerplate, markdown, and bullet points.\n\n"
        f"Company: {company_name}\n"
        f"Title: {title}\n"
        f"Article Content:\n{content[:max_content_chars]}"
    )


def ai_summary(client, model: str, company_name: str, title: str, content: str) -> dict[str, str | None]:
    prompt = summary_prompt(company_name, title, content)
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    payload = parse_json_object(response.output_text)
    return {
        "article_summary": normalize_whitespace(str(payload.get("article_summary") or "")),
        "key_topic": normalize_whitespace(str(payload.get("key_topic") or "")) or None,
        "business_impact": normalize_whitespace(str(payload.get("business_impact") or "")) or None,
        "geography": normalize_whitespace(str(payload.get("geography") or "")) or None,
        "signal_type": normalize_whitespace(str(payload.get("signal_type") or "")) or None,
    }


def ollama_summary(model: str, company_name: str, title: str, content: str) -> dict[str, str | None]:
    payload = parse_json_object(ollama_generate(summary_prompt(company_name, title, content), model, json_mode=True))
    return {
        "article_summary": normalize_whitespace(str(payload.get("article_summary") or "")),
        "key_topic": normalize_whitespace(str(payload.get("key_topic") or "")) or None,
        "business_impact": normalize_whitespace(str(payload.get("business_impact") or "")) or None,
        "geography": normalize_whitespace(str(payload.get("geography") or "")) or None,
        "signal_type": normalize_whitespace(str(payload.get("signal_type") or "")) or None,
    }


def ensure_summary_table() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS tech.tech_article_summary (
                    article_id TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT,
                    article_summary TEXT NOT NULL,
                    key_topic TEXT,
                    business_impact TEXT,
                    geography TEXT,
                    signal_type TEXT,
                    content_hash TEXT NOT NULL,
                    summary_model TEXT NOT NULL,
                    summary_status TEXT NOT NULL,
                    error_message TEXT,
                    summarized_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        connection.execute(text("ALTER TABLE tech.tech_article_summary ADD COLUMN IF NOT EXISTS key_topic TEXT"))
        connection.execute(text("ALTER TABLE tech.tech_article_summary ADD COLUMN IF NOT EXISTS business_impact TEXT"))
        connection.execute(text("ALTER TABLE tech.tech_article_summary ADD COLUMN IF NOT EXISTS geography TEXT"))
        connection.execute(text("ALTER TABLE tech.tech_article_summary ADD COLUMN IF NOT EXISTS signal_type TEXT"))


def upsert_summary(row: dict) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO tech.tech_article_summary (
                    article_id, company_name, url, title, article_summary, key_topic,
                    business_impact, geography, signal_type, content_hash,
                    summary_model, summary_status, error_message, summarized_at
                ) VALUES (
                    :article_id, :company_name, :url, :title, :article_summary, :key_topic,
                    :business_impact, :geography, :signal_type, :content_hash,
                    :summary_model, :summary_status, :error_message, :summarized_at
                )
                ON CONFLICT (article_id) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    url = EXCLUDED.url,
                    title = EXCLUDED.title,
                    article_summary = EXCLUDED.article_summary,
                    key_topic = EXCLUDED.key_topic,
                    business_impact = EXCLUDED.business_impact,
                    geography = EXCLUDED.geography,
                    signal_type = EXCLUDED.signal_type,
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
                FROM tech.tech_article_summary
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


def run(limit: int | None = None, company_name: str | None = None) -> tuple[int, int]:
    ensure_summary_table()
    articles = fetch_articles_for_summarization()
    if company_name:
        articles = articles[articles["company_name"].astype(str).str.upper() == company_name.strip().upper()]
    if limit is not None:
        articles = articles.head(limit)

    existing_summaries = load_existing_summaries()
    provider = llm_provider()
    openai = openai_client() if provider == "openai" else None
    openai_target_model = openai_model()
    ollama_target_model = ollama_summary_model()
    target_ai_model = (
        f"openai:{openai_target_model}:{SUMMARY_PROMPT_VERSION}"
        if openai
        else f"ollama:{ollama_target_model}:{SUMMARY_PROMPT_VERSION}"
        if provider == "ollama"
        else "fallback-extractive-v1"
    )

    processed = 0
    updated = 0

    for _, item in articles.iterrows():
        article_id = str(item["id"])
        company_name = str(item["company_name"])
        title = normalize_whitespace(str(item.get("title") or ""))
        content = normalize_whitespace(str(item.get("article_content") or ""))
        if not content:
            continue

        digest = content_hash(content)
        existing_summary = existing_summaries.get(article_id)
        should_refresh_with_ai = bool(
            provider in {"openai", "ollama"}
            and existing_summary
            and existing_summary["content_hash"] == digest
            and (
                existing_summary["summary_status"] != "ai"
                or existing_summary["summary_model"] != target_ai_model
            )
        )

        if existing_summary and existing_summary["content_hash"] == digest and not should_refresh_with_ai:
            continue

        summary_model = "fallback-extractive-v1"
        summary_status = "fallback"
        error_message = None

        try:
            if openai:
                summary_payload = ai_summary(openai, openai_target_model, company_name, title, content)
                summary_model = target_ai_model
                summary_status = "ai"
            elif provider == "ollama":
                summary_payload = ollama_summary(ollama_target_model, company_name, title, content)
                summary_model = target_ai_model
                summary_status = "ai"
            else:
                summary_payload = fallback_structured_summary(company_name, title, content)
        except Exception as exc:
            summary_payload = fallback_structured_summary(company_name, title, content)
            summary_status = "fallback"
            error_message = str(exc)

        summary_text = normalize_whitespace(str(summary_payload.get("article_summary") or ""))
        if not summary_text:
            continue

        upsert_summary(
            {
                "article_id": article_id,
                "company_name": company_name,
                "url": str(item["url"]),
                "title": title or None,
                "article_summary": summary_text,
                "key_topic": summary_payload.get("key_topic"),
                "business_impact": summary_payload.get("business_impact"),
                "geography": summary_payload.get("geography"),
                "signal_type": summary_payload.get("signal_type"),
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
    parser.add_argument("--company", default=None, help="Optional company name filter for targeted runs")
    parser.add_argument(
        "--skip-purge",
        action="store_true",
        help="Leave summarized article bodies in staging. Intended only for debugging.",
    )
    args = parser.parse_args()
    processed, updated = run(limit=args.limit, company_name=args.company)
    purged = 0 if args.skip_purge else purge_summarized_article_content()
    print(f"processed={processed} updated={updated} purged_article_content={purged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
