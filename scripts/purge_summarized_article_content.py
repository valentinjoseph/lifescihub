"""Purge full article bodies after summaries have been generated."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.news_catalog import discover_staging_tables
from db.session import engine


def purge_summarized_article_content() -> int:
    """Remove retained article text for articles with a usable summary."""
    purged = 0
    with engine.begin() as connection:
        for item in discover_staging_tables():
            result = connection.execute(
                text(
                    f'''
                    UPDATE "{item["schema"]}"."{item["table"]}" AS staging
                    SET article_content = NULL
                    WHERE article_content IS NOT NULL
                      AND EXISTS (
                          SELECT 1
                          FROM tech.tech_article_summary AS summary
                          WHERE summary.article_id = staging.id
                            AND COALESCE(NULLIF(summary.article_summary, ''), '') <> ''
                      )
                    '''
                )
            )
            purged += int(result.rowcount or 0)
    return purged


def main() -> int:
    purged = purge_summarized_article_content()
    print(f"purged_article_content={purged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
