from __future__ import annotations

import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts import purge_summarized_article_content


class PurgeArticleContentTests(unittest.TestCase):
    def test_purge_nulls_content_for_summarized_articles_across_staging_tables(self) -> None:
        connection = MagicMock()
        connection.execute.side_effect = [
            SimpleNamespace(rowcount=2),
            SimpleNamespace(rowcount=3),
        ]

        @contextmanager
        def fake_begin():
            yield connection

        tables = [
            {"schema": "stg_lifescience", "table": "stg_sanofi"},
            {"schema": "stg_lifescience", "table": "stg_viatris"},
        ]

        with patch.object(purge_summarized_article_content.engine, "begin", fake_begin), patch.object(
            purge_summarized_article_content,
            "discover_staging_tables",
            return_value=tables,
        ):
            purged = purge_summarized_article_content.purge_summarized_article_content()

        self.assertEqual(purged, 5)
        self.assertEqual(connection.execute.call_count, 2)
        first_sql = str(connection.execute.call_args_list[0].args[0])
        self.assertIn("SET article_content = NULL", first_sql)
        self.assertIn("tech.ls_article_summary", first_sql)
        self.assertIn("summary.article_id = staging.id", first_sql)


if __name__ == "__main__":
    unittest.main()
