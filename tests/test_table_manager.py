from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from db.table_manager import PostgresTableManager


class TableManagerTests(unittest.TestCase):
    def test_merge_company_data_passes_all_scraped_rows_to_insert_layer(self) -> None:
        manager = PostgresTableManager()
        frame = pd.DataFrame(
            [
                {
                    "id": "1",
                    "url": "https://example.com/a",
                    "title": "Article A",
                    "article_content": "Content A",
                    "published_date": "2026-04-19T00:00:00+00:00",
                    "s_created_ts": "2026-04-19T00:05:00+00:00",
                },
                {
                    "id": "2",
                    "url": "https://example.com/b",
                    "title": "Article B",
                    "article_content": "Content B",
                    "published_date": "2026-04-18T00:00:00+00:00",
                    "s_created_ts": "2026-04-19T00:06:00+00:00",
                },
            ]
        )

        with patch.object(manager, "insert_rows", return_value=2) as insert_rows:
            inserted = manager.merge_company_data("stg_ls_testco", "stg_testco_ingest", frame)

        self.assertEqual(inserted, 2)
        insert_rows.assert_called_once()
        schema, table, rows = insert_rows.call_args.args
        self.assertEqual(schema, "stg_ls_testco")
        self.assertEqual(table, "stg_testco_ingest")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["url"], "https://example.com/a")
        self.assertEqual(rows[1]["title"], "Article B")


if __name__ == "__main__":
    unittest.main()
