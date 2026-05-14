from __future__ import annotations

import unittest
from datetime import datetime, UTC
from unittest.mock import patch

from core.scraper import scrape_source


class FakeResponse:
    def __init__(self, url: str, text: str, status_code: int = 200, content_type: str = "text/html; charset=UTF-8"):
        self.url = url
        self.text = text
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


class FakeSession:
    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses
        self.headers = {"User-Agent": "TestAgent/1.0"}

    def get(self, url: str, timeout: int = 20) -> FakeResponse:
        return self.responses[url]


class ScrapeSourceTests(unittest.TestCase):
    def test_scrape_source_retrieves_article_records_from_listing_page(self) -> None:
        listing_url = "https://example.com/news"
        article_url = "https://example.com/news/article-1"
        listing_html = f"""
        <html>
          <body>
            <article><a href="{article_url}">Read more</a></article>
          </body>
        </html>
        """
        article_html = """
        <html>
          <head>
            <title>Test Article</title>
            <meta property="article:published_time" content="2026-04-19T09:00:00+00:00" />
          </head>
          <body>
            <article>
              <p>This is the first paragraph of a valid article body.</p>
              <p>This is the second paragraph with enough content to pass validation.</p>
            </article>
          </body>
        </html>
        """
        fake_session = FakeSession(
            {
                listing_url: FakeResponse(listing_url, listing_html),
                article_url: FakeResponse(article_url, article_html),
            }
        )
        config = {
            "MAX_ITEMS_PER_SOURCE": 10,
            "LISTING_SLEEP_SEC": 0,
            "ARTICLE_SLEEP_SEC": 0,
            "REQUEST_TIMEOUT_SEC": 10,
        }

        with patch("core.scraper.make_session", return_value=fake_session), patch(
            "core.scraper.can_fetch_url", return_value=True
        ):
            records, metrics = scrape_source("TESTCO", listing_url, config)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["company_name"], "TESTCO")
        self.assertEqual(records[0]["url"], article_url)
        self.assertIn("Test Article", records[0]["title"])
        self.assertEqual(metrics["urls_fetched"], 2)
        self.assertEqual(metrics["parse_success_count"], 1)

    def test_scrape_source_skips_jsonld_articles_before_delta_cutoff(self) -> None:
        listing_url = "https://example.com/news"
        old_article_url = "https://example.com/news/old"
        new_article_url = "https://example.com/news/new"
        listing_html = f"""
        <html>
          <head>
            <script type="application/ld+json">
              [
                {{
                  "@type": "NewsArticle",
                  "url": "{old_article_url}",
                  "headline": "Old Article",
                  "datePublished": "2026-04-19T09:00:00+00:00"
                }},
                {{
                  "@type": "NewsArticle",
                  "url": "{new_article_url}",
                  "headline": "New Article",
                  "datePublished": "2026-04-19T11:00:00+00:00"
                }}
              ]
            </script>
          </head>
          <body></body>
        </html>
        """
        new_article_html = """
        <html>
          <head>
            <title>New Article</title>
            <meta property="article:published_time" content="2026-04-19T11:00:00+00:00" />
          </head>
          <body>
            <article>
              <p>This is the first paragraph of a valid article body.</p>
              <p>This is the second paragraph with enough content to pass validation.</p>
            </article>
          </body>
        </html>
        """
        fake_session = FakeSession(
            {
                listing_url: FakeResponse(listing_url, listing_html),
                new_article_url: FakeResponse(new_article_url, new_article_html),
            }
        )
        config = {
            "MAX_ITEMS_PER_SOURCE": 10,
            "LISTING_SLEEP_SEC": 0,
            "ARTICLE_SLEEP_SEC": 0,
            "REQUEST_TIMEOUT_SEC": 10,
        }

        with patch("core.scraper.make_session", return_value=fake_session), patch(
            "core.scraper.can_fetch_url", return_value=True
        ):
            records, metrics = scrape_source(
                "TESTCO",
                listing_url,
                config,
                min_published_date=datetime(2026, 4, 19, 10, 0, tzinfo=UTC),
            )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["url"], new_article_url)
        self.assertEqual(metrics["urls_fetched"], 2)

    def test_scrape_source_keeps_articles_without_dates_in_delta(self) -> None:
        listing_url = "https://example.com/news"
        article_url = "https://example.com/news/unknown-date"
        listing_html = f"""
        <html>
          <body>
            <article><a href="{article_url}">Read more</a></article>
          </body>
        </html>
        """
        article_html = """
        <html>
          <head>
            <title>Unknown Date Article</title>
          </head>
          <body>
            <article>
              <p>This is the first paragraph of a valid article body.</p>
              <p>This is the second paragraph with enough content to pass validation.</p>
            </article>
          </body>
        </html>
        """
        fake_session = FakeSession(
            {
                listing_url: FakeResponse(listing_url, listing_html),
                article_url: FakeResponse(article_url, article_html),
            }
        )
        config = {
            "MAX_ITEMS_PER_SOURCE": 10,
            "LISTING_SLEEP_SEC": 0,
            "ARTICLE_SLEEP_SEC": 0,
            "REQUEST_TIMEOUT_SEC": 10,
        }

        with patch("core.scraper.make_session", return_value=fake_session), patch(
            "core.scraper.can_fetch_url", return_value=True
        ):
            records, _ = scrape_source(
                "TESTCO",
                listing_url,
                config,
                min_published_date=datetime(2026, 4, 19, 10, 0, tzinfo=UTC),
            )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["url"], article_url)
        self.assertIsNone(records[0]["published_date"])


if __name__ == "__main__":
    unittest.main()
