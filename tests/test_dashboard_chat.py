from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from app import ChatRequest, dashboard_chat, dashboard_news
from core.dashboard import fetch_dashboard_payload


class DashboardChatTests(unittest.TestCase):
    def test_dashboard_chat_ignores_news_feed_company_filter(self) -> None:
        with patch("app.chat_about_news") as chat_about_news:
            chat_about_news.return_value = {
                "answer": "ok",
                "model": "test",
                "article_count": 0,
                "sources": [],
            }

            dashboard_chat(ChatRequest(question="What changed?", company_name="SANOFI", period="month"))

        chat_about_news.assert_called_once_with(
            question="What changed?",
            company_name="ALL",
            period="month",
        )

    def test_dashboard_news_passes_topic_filter_to_payload(self) -> None:
        with patch("app.fetch_dashboard_payload") as fetch_dashboard_payload:
            fetch_dashboard_payload.return_value = {"rows": []}

            response = dashboard_news(company="SANOFI", period="month", topic="financial")

        self.assertEqual(response, {"rows": []})
        fetch_dashboard_payload.assert_called_once_with(
            company_name="SANOFI",
            period="month",
            topic="financial",
        )

    def test_dashboard_payload_applies_company_and_topic_filters(self) -> None:
        news_frame = pd.DataFrame(
            [
                {
                    "company_name": "SANOFI",
                    "published_date": pd.Timestamp("2026-04-20", tz="UTC"),
                    "priority_score": 88,
                    "title": "Financial update",
                    "article_summary": "Summary",
                    "key_topic": "financial",
                    "business_impact": "Impact",
                    "geography": "Global",
                    "signal_type": "earnings",
                    "url": "https://example.com",
                    "summary_status": "ok",
                }
            ]
        )

        with patch("core.dashboard.list_companies", return_value=["SANOFI"]), patch(
            "core.dashboard.list_topics",
            return_value=["financial"],
        ) as list_topics, patch("core.dashboard.fetch_news", return_value=news_frame) as fetch_news:
            payload = fetch_dashboard_payload(company_name="SANOFI", period="month", topic="financial")

        list_topics.assert_called_once_with(period="month", company_name="SANOFI")
        fetch_news.assert_called_once_with(
            company_name="SANOFI",
            period="month",
            topic="financial",
            limit=200,
        )
        self.assertEqual(payload["filters"]["selected_topic"], "financial")
        self.assertEqual(payload["filters"]["topics"], ["ALL", "financial"])
        self.assertEqual(payload["summary"]["article_count"], 1)

    def test_dashboard_payload_handles_articles_without_published_dates(self) -> None:
        news_frame = pd.DataFrame(
            [
                {
                    "company_name": "SANOFI",
                    "published_date": pd.NaT,
                    "priority_score": 72,
                    "title": "Undated update",
                    "article_summary": "Summary",
                    "key_topic": "financial",
                    "business_impact": "Impact",
                    "geography": "Global",
                    "signal_type": "earnings",
                    "url": "https://example.com",
                    "summary_status": "ok",
                }
            ]
        )

        with patch("core.dashboard.list_companies", return_value=["SANOFI"]), patch(
            "core.dashboard.list_topics",
            return_value=["financial"],
        ), patch("core.dashboard.fetch_news", return_value=news_frame):
            payload = fetch_dashboard_payload(company_name="ALL", period="all", topic="ALL")

        self.assertEqual(payload["rows"][0]["published_date"], "")


if __name__ == "__main__":
    unittest.main()
