"""Tests for daily monitoring report formatting and email setup."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scripts import send_daily_monitoring_report


class DailyMonitoringReportTests(unittest.TestCase):
    def test_parse_recipients_accepts_commas_and_semicolons(self) -> None:
        self.assertEqual(
            send_daily_monitoring_report.parse_recipients("ops@example.com; user@outlook.com, admin@example.com"),
            ["ops@example.com", "user@outlook.com", "admin@example.com"],
        )

    def test_report_includes_company_insert_counts_and_pipeline_status(self) -> None:
        body = send_daily_monitoring_report.format_monitoring_report(
            rows=[
                {
                    "run_id": "run-1",
                    "company_name": "SANOFI",
                    "load_type": "DELTA",
                    "run_status": "SUCCESS",
                    "run_message": "Loaded",
                    "records_inserted": 3,
                    "urls_attempted": 10,
                    "urls_fetched": 9,
                    "parse_success_count": 8,
                    "error_count": 1,
                },
                {
                    "run_id": "run-1",
                    "company_name": "PFIZER",
                    "load_type": "DELTA",
                    "run_status": "SUCCESS",
                    "run_message": "Loaded",
                    "records_inserted": 0,
                    "urls_attempted": 5,
                    "urls_fetched": 5,
                    "parse_success_count": 5,
                    "error_count": 0,
                },
            ],
            report_date="2026-05-13",
            pipeline_status="SUCCESS",
            exit_code=0,
            started_at="2026-05-13T06:00:00Z",
            ended_at="2026-05-13T06:02:00Z",
        )

        self.assertIn("Pipeline status: SUCCESS", body)
        self.assertIn("Total records inserted: 3", body)
        self.assertIn("company name | status", body)
        self.assertIn("fetched", body)
        self.assertIn("parsed", body)
        self.assertIn("attempted", body)
        self.assertIn("inserted", body)
        self.assertIn("errors", body)
        self.assertIn("SANOFI", body)
        self.assertIn("SUCCESS", body)
        self.assertIn("3", body)

    def test_empty_report_explains_scraper_did_not_write_monitoring_rows(self) -> None:
        body = send_daily_monitoring_report.format_monitoring_report(
            rows=[],
            report_date="2026-05-13",
            pipeline_status="FAILED",
            exit_code=1,
            started_at="2026-05-13T06:00:00Z",
            ended_at="2026-05-13T06:01:00Z",
        )

        self.assertIn("Pipeline status: FAILED", body)
        self.assertIn("No rows were found in tech.tech_load_monitoring", body)

    def test_html_report_uses_table_and_highlight_colors(self) -> None:
        html = send_daily_monitoring_report.format_monitoring_report_html(
            rows=[
                {
                    "run_id": "run-1",
                    "company_name": "SANOFI",
                    "load_type": "DELTA",
                    "run_status": "SUCCESS",
                    "records_inserted": 3,
                    "urls_attempted": 10,
                    "urls_fetched": 9,
                    "parse_success_count": 8,
                    "error_count": 0,
                },
                {
                    "run_id": "run-1",
                    "company_name": "PFIZER",
                    "load_type": "DELTA",
                    "run_status": "SUCCESS",
                    "records_inserted": 0,
                    "urls_attempted": 5,
                    "urls_fetched": 4,
                    "parse_success_count": 4,
                    "error_count": 1,
                },
            ],
            report_date="2026-05-13",
            pipeline_status="SUCCESS",
            exit_code=0,
            started_at="2026-05-13T06:00:00Z",
            ended_at="2026-05-13T06:02:00Z",
        )

        self.assertIn("<table", html)
        self.assertIn("company name", html)
        self.assertIn("background: #dcfce7", html)
        self.assertIn("background: #fee2e2", html)
        self.assertIn("<td", html)

    def test_build_message_includes_html_alternative(self) -> None:
        message = send_daily_monitoring_report.build_message("subject", "plain", "<table></table>")

        self.assertTrue(message.is_multipart())
        self.assertIsNotNone(message.get_body(preferencelist=("html",)))

    def test_main_skips_when_email_disabled(self) -> None:
        with patch.dict(os.environ, {"DAILY_REPORT_EMAIL_ENABLED": "false"}, clear=True):
            with patch.object(send_daily_monitoring_report, "send_message") as send_message:
                result = send_daily_monitoring_report.main_with_args(
                    [
                        "--pipeline-status",
                        "SUCCESS",
                        "--exit-code",
                        "0",
                        "--started-at",
                        "2026-05-13T06:00:00Z",
                        "--ended-at",
                        "2026-05-13T06:01:00Z",
                    ]
                )

        self.assertEqual(result, 0)
        send_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
