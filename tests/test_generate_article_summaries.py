from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from scripts import generate_article_summaries


class GenerateArticleSummariesTests(unittest.TestCase):
    def test_main_purges_article_content_after_summary_generation_by_default(self) -> None:
        with patch.object(sys, "argv", ["generate_article_summaries.py"]), patch.object(
            generate_article_summaries,
            "run",
            return_value=(2, 2),
        ), patch.object(
            generate_article_summaries,
            "purge_summarized_article_content",
            return_value=2,
        ) as purge:
            exit_code = generate_article_summaries.main()

        self.assertEqual(exit_code, 0)
        purge.assert_called_once_with()

    def test_main_can_skip_purge_for_debugging(self) -> None:
        with patch.object(sys, "argv", ["generate_article_summaries.py", "--skip-purge"]), patch.object(
            generate_article_summaries,
            "run",
            return_value=(2, 2),
        ), patch.object(generate_article_summaries, "purge_summarized_article_content") as purge:
            exit_code = generate_article_summaries.main()

        self.assertEqual(exit_code, 0)
        purge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
