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
        self.assertIn("schemaname LIKE 'stg_ls_%'", sql)
        self.assertIn("tablename LIKE 'stg_%_ingest'", sql)
        self.assertIn("FROM dwh.f_news_staging_articles()", sql)

    def test_v_news_all_does_not_hardcode_company_staging_tables(self) -> None:
        sql = DWH_SQL.read_text(encoding="utf-8")

        self.assertNotIn("FROM stg_ls_alliance_healthcare.stg_alliance_healthcare_ingest", sql)
        self.assertNotIn("FROM stg_ls_sanofi.stg_sanofi_ingest", sql)
        self.assertNotIn("FROM stg_ls_virbac.stg_virbac_ingest", sql)
