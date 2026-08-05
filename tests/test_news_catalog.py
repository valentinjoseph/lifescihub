from __future__ import annotations

import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from db import news_catalog


class NewsCatalogTests(unittest.TestCase):
    def test_discover_staging_tables_scans_all_stg_prefixed_schemas_and_tables(self) -> None:
        result = MagicMock()
        result.mappings.return_value.all.return_value = [
            {"schemaname": "stg_lifescience", "tablename": "stg_sanofi"},
            {"schemaname": "STG_BANKING", "tablename": "STG_HSBC"},
        ]
        connection = MagicMock()
        connection.execute.return_value = result

        @contextmanager
        def fake_begin():
            yield connection

        with patch.object(news_catalog.engine, "begin", fake_begin):
            tables = news_catalog.discover_staging_tables()

        discovery_sql = str(connection.execute.call_args.args[0])
        self.assertIn("schemaname ILIKE 'stg%'", discovery_sql)
        self.assertIn("tablename ILIKE 'stg%'", discovery_sql)
        self.assertEqual(
            tables,
            [
                {
                    "schema": "stg_lifescience",
                    "table": "stg_sanofi",
                    "company_name": "SANOFI",
                    "industry_sector": "LIFESCIENCE",
                },
                {
                    "schema": "STG_BANKING",
                    "table": "STG_HSBC",
                    "company_name": "HSBC",
                    "industry_sector": "BANKING",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
