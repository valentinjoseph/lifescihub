"""Regression checks for reporting-view SQL."""

from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DWH_SQL = PROJECT_ROOT / "config" / "scripts" / "dwh_views.sql"


class DwhViewsSqlTest(unittest.TestCase):
    def test_v_news_all_uses_dynamic_staging_discovery(self) -> None:
        sql = DWH_SQL.read_text(encoding="utf-8")

        self.assertIn("CREATE OR REPLACE FUNCTION dwh.f_news_staging_articles()", sql)
        self.assertIn("FROM pg_tables", sql)
        self.assertIn("schemaname ILIKE 'stg%'", sql)
        self.assertIn("tablename ILIKE 'stg%'", sql)
        self.assertIn("regexp_replace(staging_table.schemaname, '^stg_', '', 'i')", sql)
        self.assertIn("industry_sector TEXT", sql)
        self.assertIn("FROM dwh.f_news_staging_articles()", sql)

    def test_v_news_all_does_not_hardcode_company_staging_tables(self) -> None:
        sql = DWH_SQL.read_text(encoding="utf-8")

        self.assertNotIn("FROM stg_lifescience.stg_sanofi", sql)
        self.assertNotIn("FROM stg_banking.stg_test_bank", sql)
        self.assertNotIn("FROM stg_energy.stg_test_energy", sql)
        self.assertNotIn("schemaname = 'stg_lifescience'", sql)
        self.assertNotIn("schemaname = 'stg_banking'", sql)

    def test_reporting_views_do_not_expose_full_article_content(self) -> None:
        sql = DWH_SQL.read_text(encoding="utf-8")

        self.assertNotIn("article_content", sql)
