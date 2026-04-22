"""Dashboard data access and chat helpers."""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

import pandas as pd
from openai import OpenAI
from sqlalchemy import text

from db.session import engine


PERIOD_TO_VIEW = {
    "week": "dwh.v_news_week_export",
    "month": "dwh.v_news_month_export",
    "6_months": "dwh.v_news_6_months_export",
    "all": "dwh.v_news_all_export",
}

PERIOD_LABELS = {
    "week": "Last 7 days",
    "month": "This month",
    "6_months": "Last 6 months",
    "all": "All available",
}


def available_periods() -> list[dict[str, str]]:
    return [{"value": key, "label": label} for key, label in PERIOD_LABELS.items()]


def _format_date(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def list_companies(period: str = "all") -> list[str]:
    view_name = _resolve_view(period)
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                f"""
                SELECT DISTINCT company_name
                FROM {view_name}
                ORDER BY company_name
                """
            )
        ).mappings().all()
    return [str(row["company_name"]) for row in rows]


def list_topics(period: str = "all", company_name: str | None = None) -> list[str]:
    view_name = _resolve_view(period)
    clauses = ["COALESCE(NULLIF(key_topic, ''), '') <> ''"]
    params: dict[str, Any] = {}
    if company_name and company_name.upper() != "ALL":
        clauses.append("company_name = :company_name")
        params["company_name"] = company_name
    where_clause = f"WHERE {' AND '.join(clauses)}"
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                f"""
                SELECT DISTINCT key_topic
                FROM {view_name}
                {where_clause}
                ORDER BY key_topic
                """
            ),
            params,
        ).mappings().all()
    return [str(row["key_topic"]) for row in rows]


def _resolve_view(period: str) -> str:
    return PERIOD_TO_VIEW.get(period, PERIOD_TO_VIEW["week"])


def fetch_news(
    company_name: str | None = None,
    period: str = "week",
    topic: str | None = None,
    limit: int = 200,
) -> pd.DataFrame:
    view_name = _resolve_view(period)
    clauses = []
    params: dict[str, Any] = {"limit": int(limit)}
    if company_name and company_name.upper() != "ALL":
        clauses.append("company_name = :company_name")
        params["company_name"] = company_name
    if topic and topic.upper() != "ALL":
        clauses.append("key_topic = :topic")
        params["topic"] = topic
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = text(
        f"""
        SELECT
            company_name,
            published_date,
            priority_score,
            title,
            article_summary,
            key_topic,
            business_impact,
            geography,
            signal_type,
            url,
            summary_status
        FROM {view_name}
        {where_clause}
        ORDER BY priority_score DESC, published_date DESC NULLS LAST, company_name ASC
        LIMIT :limit
        """
    )
    with engine.begin() as connection:
        frame = pd.read_sql_query(query, connection, params=params)
    if frame.empty:
        return frame
    frame["published_date"] = pd.to_datetime(frame["published_date"], utc=True, errors="coerce")
    return frame.fillna("")


def fetch_dashboard_payload(
    company_name: str | None = None,
    period: str = "week",
    topic: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    companies = list_companies(period=period)
    selected_company = company_name or "ALL"
    if selected_company.upper() != "ALL" and selected_company not in companies:
        selected_company = "ALL"

    topics = list_topics(period=period, company_name=selected_company)
    selected_topic = topic or "ALL"
    if selected_topic.upper() != "ALL" and selected_topic not in topics:
        selected_topic = "ALL"

    news_df = fetch_news(company_name=selected_company, period=period, topic=selected_topic, limit=limit)

    if news_df.empty:
        return {
            "filters": {
                "selected_company": selected_company,
                "selected_period": period,
                "selected_topic": selected_topic,
                "companies": ["ALL", *companies],
                "periods": available_periods(),
                "topics": ["ALL", *topics],
            },
            "summary": {
                "article_count": 0,
                "company_count": 0,
                "avg_priority": 0,
                "top_topics": [],
            },
            "rows": [],
        }

    top_topics = (
        news_df["key_topic"]
        .replace("", pd.NA)
        .dropna()
        .value_counts()
        .head(5)
        .reset_index()
        .to_dict(orient="records")
    )
    rows = news_df.to_dict(orient="records")
    for row in rows:
        row["published_date"] = _format_date(row.get("published_date"))

    return {
        "filters": {
            "selected_company": selected_company,
            "selected_period": period,
            "selected_topic": selected_topic,
            "companies": ["ALL", *companies],
            "periods": available_periods(),
            "topics": ["ALL", *topics],
        },
        "summary": {
            "article_count": int(len(news_df)),
            "company_count": int(news_df["company_name"].nunique()),
            "avg_priority": round(float(news_df["priority_score"].mean()), 1),
            "top_topics": top_topics,
        },
        "rows": rows,
    }


def _fallback_chat_answer(question: str, articles: pd.DataFrame, company_name: str | None, period: str) -> str:
    period_label = PERIOD_LABELS.get(period, period)
    if articles.empty:
        target = company_name or "the selected companies"
        return f"I do not see any articles for {target} in {period_label.lower()}."

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in articles.to_dict(orient="records"):
        grouped[str(row["company_name"])].append(row)

    lines = [
        f"Here is the latest view for {company_name or 'all companies'} in {period_label.lower()}.",
        "",
    ]
    for company, items in sorted(grouped.items()):
        lines.append(f"{company}: {len(items)} article(s)")
        for item in items[:3]:
            date_label = _format_date(item.get("published_date"))
            summary = str(item.get("article_summary") or "").strip()
            title = str(item.get("title") or "").strip()
            impact = str(item.get("business_impact") or "").strip()
            lines.append(f"- {date_label} | {title}")
            if summary:
                lines.append(f"  Summary: {summary}")
            if impact:
                lines.append(f"  Why it matters: {impact}")
        if len(items) > 3:
            lines.append(f"  ... plus {len(items) - 3} more article(s).")
        lines.append("")

    question_clean = question.strip()
    if question_clean:
        lines.append(f"Question asked: {question_clean}")
    return "\n".join(lines).strip()


def _article_sources(articles: pd.DataFrame, limit: int = 12) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    if articles.empty:
        return sources

    for item in articles.head(limit).to_dict(orient="records"):
        date_label = _format_date(item.get("published_date"))
        sources.append(
            {
                "company_name": item.get("company_name", ""),
                "published_date": date_label,
                "title": item.get("title", ""),
                "article_summary": item.get("article_summary", ""),
                "business_impact": item.get("business_impact", ""),
                "priority_score": item.get("priority_score", ""),
                "url": item.get("url", ""),
            }
        )
    return sources


def chat_about_news(question: str, company_name: str | None = None, period: str = "week", limit: int = 60) -> dict[str, Any]:
    articles = fetch_news(company_name=company_name, period=period, limit=limit)
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")

    if articles.empty:
        return {
            "answer": _fallback_chat_answer(question, articles, company_name, period),
            "model": "fallback-dashboard-v1",
            "article_count": 0,
            "sources": [],
        }

    if not api_key:
        return {
            "answer": _fallback_chat_answer(question, articles, company_name, period),
            "model": "fallback-dashboard-v1",
            "article_count": int(len(articles)),
            "sources": _article_sources(articles),
        }

    client = OpenAI(api_key=api_key)
    context_rows = []
    for item in articles.head(limit).to_dict(orient="records"):
        date_label = _format_date(item.get("published_date"))
        context_rows.append(
            {
                "company_name": item["company_name"],
                "published_date": date_label,
                "priority_score": item["priority_score"],
                "title": item["title"],
                "article_summary": item["article_summary"],
                "business_impact": item["business_impact"],
                "key_topic": item["key_topic"],
                "signal_type": item["signal_type"],
                "url": item["url"],
            }
        )

    prompt = (
        "You are a reporting assistant for a life-sciences business watch dashboard. "
        "Answer only from the provided article context. "
        "Be concise but useful. Group by company when relevant. "
        "If the user asks for news this week or similar, list company-by-company highlights. "
        "Mention titles, timing, and why the item matters. "
        "If there is no relevant information in the context, say so clearly.\n\n"
        f"Selected company filter: {company_name or 'ALL'}\n"
        f"Selected period filter: {PERIOD_LABELS.get(period, period)}\n"
        f"User question: {question}\n\n"
        "Article context JSON:\n"
        f"{context_rows}"
    )
    response = client.responses.create(model=model, input=prompt)
    return {
        "answer": response.output_text.strip(),
        "model": model,
        "article_count": int(len(articles)),
        "sources": _article_sources(articles),
    }
