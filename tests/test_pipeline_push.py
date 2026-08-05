from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, UTC

import pandas as pd

from orchestration.LS_MAIN_REFACTORED import filter_delta_records, run_pipeline


class FakeScrapingConfig:
    def __init__(self, config_path, overrides=None):
        self.config_path = Path(config_path)
        self.config = {
            "MAX_ITEMS_PER_SOURCE": 10,
            "MAX_WORKERS": 1,
            "LISTING_SLEEP_SEC": 0,
            "ARTICLE_SLEEP_SEC": 0,
            "REQUEST_TIMEOUT_SEC": 10,
            "MIN_TITLE_LENGTH": 10,
            "EXPORT_RESULTS": False,
        }
        if overrides:
            self.config.update({key: value for key, value in overrides.items() if value is not None})

    def ensure_file(self):
        return self.config_path

    def get_worker_count(self) -> int:
        return int(self.config["MAX_WORKERS"])

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def __getitem__(self, key: str):
        return self.config[key]


class FakeMonitor:
    def __init__(self, flow_name: str, run_id: str):
        self.flow_name = flow_name
        self.run_id = run_id
        self.logged: list[dict[str, object]] = []

    def get_last_success_timestamp(self, company_name: str):
        del company_name
        return None

    def log_completion(self, **kwargs) -> None:
        self.logged.append(kwargs)


class PipelinePushTests(unittest.TestCase):
    def test_filter_delta_records_keeps_new_and_unknown_date_articles(self) -> None:
        frame = pd.DataFrame(
            [
                {"url": "https://example.com/old", "published_date": "2026-04-19T09:59:59+00:00"},
                {"url": "https://example.com/equal", "published_date": "2026-04-19T10:00:00+00:00"},
                {"url": "https://example.com/new", "published_date": "2026-04-19T10:00:01+00:00"},
                {"url": "https://example.com/unknown", "published_date": None},
            ]
        )

        filtered = filter_delta_records(frame, datetime(2026, 4, 19, 10, 0, tzinfo=UTC))

        self.assertEqual(list(filtered["url"]), ["https://example.com/new", "https://example.com/unknown"])

    def test_run_pipeline_pushes_validated_scraped_rows_to_merge_layer(self) -> None:
        scraped_records = [
            {
                "company_name": "TESTCO",
                "id": "row-1",
                "source_url": "https://example.com/news",
                "url": "https://example.com/news/article-1",
                "title": "A valid article title",
                "article_content": "Long enough content for the pipeline to accept and push.",
                "published_date": "2026-04-19T10:00:00+00:00",
                "s_created_ts": "2026-04-19T10:01:00+00:00",
                "response_time_ms": 101.0,
            }
        ]
        scrape_metrics = {
            "urls_attempted": 2,
            "urls_fetched": 2,
            "parse_success_count": 1,
            "error_count": 0,
            "avg_response_time_ms": 101.0,
        }
        company_metrics = {"TESTCO": dict(scrape_metrics)}
        merged_frames: list[tuple[str, str, pd.DataFrame]] = []

        def fake_merge_data(manager, catalog, schema, table, source_df):
            del manager, catalog
            merged_frames.append((schema, table, source_df.copy()))
            return len(source_df)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            args = Namespace(
                sources=str(tmp_path / "sources.csv"),
                load_config=str(tmp_path / "load_config.csv"),
                scraping_config=str(tmp_path / "scraping_config.json"),
                db_path=str(tmp_path / "gtm_advisor.db"),
                output_dir=str(tmp_path / "outputs"),
                max_workers=1,
                dry_run=False,
                verbose=False,
            )

            with patch("orchestration.LS_MAIN_REFACTORED.ScrapingConfig", FakeScrapingConfig), patch(
                "orchestration.LS_MAIN_REFACTORED.bootstrap_postgres"
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.load_sources",
                return_value=[{"company_name": "TESTCO", "url": "https://example.com/news"}],
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.load_company_config",
                return_value={"TESTCO": {"load_type": "FULL", "industry_sector": "LIFESCIENCE"}},
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.PostgresTableManager"
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.ScrapingMonitor", FakeMonitor
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.scrape_sources",
                return_value=(scraped_records, scrape_metrics, company_metrics),
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.ensure_schema_and_table"
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.merge_data", side_effect=fake_merge_data
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.update_successful_companies_to_delta"
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.export_results"
            ):
                exit_code = run_pipeline(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(merged_frames), 1)

        schema, table, merged_df = merged_frames[0]
        self.assertEqual(schema, "stg_lifescience")
        self.assertEqual(table, "stg_testco")
        self.assertEqual(len(merged_df), 1)
        self.assertEqual(
            list(merged_df.columns),
            ["id", "url", "title", "article_content", "published_date", "s_created_ts"],
        )
        self.assertEqual(merged_df.iloc[0]["url"], "https://example.com/news/article-1")
        self.assertEqual(merged_df.iloc[0]["title"], "A valid article title")

    def test_delta_pipeline_logs_post_delta_metrics(self) -> None:
        scraped_records = [
            {
                "company_name": "TESTCO",
                "id": "old-row",
                "source_url": "https://example.com/news",
                "url": "https://example.com/news/old",
                "title": "An old article title",
                "article_content": "Long enough content for the pipeline to accept and push.",
                "published_date": "2026-04-19T09:00:00+00:00",
                "s_created_ts": "2026-04-19T09:01:00+00:00",
                "response_time_ms": 99.0,
            },
            {
                "company_name": "TESTCO",
                "id": "new-row",
                "source_url": "https://example.com/news",
                "url": "https://example.com/news/new",
                "title": "A new article title",
                "article_content": "Long enough content for the pipeline to accept and push.",
                "published_date": "2026-04-19T11:00:00+00:00",
                "s_created_ts": "2026-04-19T11:01:00+00:00",
                "response_time_ms": 101.0,
            },
        ]
        scrape_metrics = {
            "urls_attempted": 8,
            "urls_fetched": 8,
            "parse_success_count": 2,
            "error_count": 0,
            "avg_response_time_ms": 100.0,
        }
        company_metrics = {"TESTCO": dict(scrape_metrics)}
        fake_monitor = None
        merged_frames: list[pd.DataFrame] = []

        class DeltaMonitor(FakeMonitor):
            def __init__(self, flow_name: str, run_id: str):
                nonlocal fake_monitor
                super().__init__(flow_name, run_id)
                fake_monitor = self

            def get_last_success_timestamp(self, company_name: str):
                del company_name
                return datetime(2026, 4, 19, 10, 0, tzinfo=UTC)

        def fake_merge_data(manager, catalog, schema, table, source_df):
            del manager, catalog, schema, table
            merged_frames.append(source_df.copy())
            return len(source_df)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            args = Namespace(
                sources=str(tmp_path / "sources.csv"),
                load_config=str(tmp_path / "load_config.csv"),
                scraping_config=str(tmp_path / "scraping_config.json"),
                db_path=str(tmp_path / "gtm_advisor.db"),
                output_dir=str(tmp_path / "outputs"),
                max_workers=1,
                dry_run=False,
                verbose=False,
            )

            with patch("orchestration.LS_MAIN_REFACTORED.ScrapingConfig", FakeScrapingConfig), patch(
                "orchestration.LS_MAIN_REFACTORED.bootstrap_postgres"
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.load_sources",
                return_value=[{"company_name": "TESTCO", "url": "https://example.com/news"}],
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.load_company_config",
                return_value={"TESTCO": {"load_type": "DELTA", "industry_sector": "LIFESCIENCE"}},
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.PostgresTableManager"
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.ScrapingMonitor", DeltaMonitor
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.scrape_sources",
                return_value=(scraped_records, scrape_metrics, company_metrics),
            ) as scrape_sources_mock, patch(
                "orchestration.LS_MAIN_REFACTORED.ensure_schema_and_table"
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.merge_data", side_effect=fake_merge_data
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.update_successful_companies_to_delta"
            ), patch(
                "orchestration.LS_MAIN_REFACTORED.export_results"
            ):
                exit_code = run_pipeline(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(list(merged_frames[0]["url"]), ["https://example.com/news/new"])
        self.assertIsNotNone(fake_monitor)
        self.assertEqual(fake_monitor.logged[0]["metrics"]["urls_fetched"], 1)
        self.assertEqual(fake_monitor.logged[0]["metrics"]["parse_success_count"], 1)
        scrape_sources_mock.assert_called_once()
        self.assertEqual(
            scrape_sources_mock.call_args.kwargs["min_published_dates"]["TESTCO"],
            datetime(2026, 4, 19, 10, 0, tzinfo=UTC),
        )


if __name__ == "__main__":
    unittest.main()
