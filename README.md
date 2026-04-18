# Life Science Watch

Life Science Watch is a local Python + PostgreSQL pipeline that scrapes configured company news sources, stages article content in Postgres, generates AI-assisted summaries, builds DWH views, and publishes a formatted Excel workbook locally and to Google Drive.

## What It Does

- reads source URLs from `tech.ls_load_sources`
- reads `FULL` / `DELTA` mode from `tech.ls_load_config`
- scrapes listing pages and article pages
- stores staged articles in company-specific schemas
- generates AI summaries plus structured fields like topic and business impact
- exposes DWH views for reporting
- exports a styled Excel workbook
- uploads the latest workbook to Google Drive

## Repo Map

```text
lifescience_watch/
├── app.py                      FastAPI wrapper for local operations
├── Makefile                    Common local commands
├── core/                       Scraper, monitoring, runtime config
├── db/                         PostgreSQL helpers and Alembic migrations
├── config/                     Runtime config loader and SQL assets
│   └── scripts/                DWH views and seed SQL
├── orchestration/              Main pipeline entrypoint
├── scripts/                    Summaries, export, sync, and daily runner
├── infra/                      Local env files
├── postgres/init/              Postgres init SQL for the tech schema
├── data/                       Local bootstrap/example files and legacy SQLite
├── outputs/                    CSV/log outputs
└── exports/                    Excel workbook exports
```

## Quick Start

```bash
cd /home/hl-lenovo/projects/lifescience_watch
make setup
source .venv/bin/activate
```

Fill in `infra/.env` after copying from `infra/.env.example`.

Useful first checks:

```bash
make dry-run
make docker-up
make health
```

## Common Commands

Use the `Makefile` for the normal workflow:

```bash
make help
make scrape
make summarize
make export
make sync
make refresh
make daily
make docker-rebuild
make psql
```

What they do:

- `make scrape`: run the scraper pipeline
- `make summarize`: refresh AI and structured summaries
- `make export`: rebuild the Excel workbook
- `make sync`: upload the latest workbook to Google Drive
- `make refresh`: summarize + export + sync
- `make daily`: run the full daily pipeline script

## Daily Automation

The daily scheduled job runs:

1. scraping
2. summary refresh
3. workbook export
4. Google Drive upload

Current cron target:

```cron
0 8 * * * /bin/bash /home/hl-lenovo/projects/lifescience_watch/scripts/run_daily_pipeline.sh >> /home/hl-lenovo/projects/lifescience_watch/outputs/run_daily_pipeline.log 2>&1
```

Manual run:

```bash
/bin/bash scripts/run_daily_pipeline.sh
```

## API Usage

The local service exposes:

- `GET /health`
- `GET /status`
- `POST /run`

All operational endpoints require the `X-Run-Token` header.

Examples:

```bash
source infra/.env

curl http://127.0.0.1:8011/health \
  -H "X-Run-Token: ${LSW_RUN_TOKEN}"

curl http://127.0.0.1:8011/status \
  -H "X-Run-Token: ${LSW_RUN_TOKEN}"

curl -X POST http://127.0.0.1:8011/run \
  -H "X-Run-Token: ${LSW_RUN_TOKEN}"
```

FastAPI docs are disabled by default when `API_ENABLE_DOCS=false`.

## Database Notes

Connection defaults:

- database: `liscihub`
- schema: `tech`
- postgres container: `liscihub-postgres`
- host port: `5434`

DBeaver over SSH tunnel:

- host: `127.0.0.1`
- port: `5434`
- database: `liscihub`
- username: `liscihub`
- password: value of `POSTGRES_PASSWORD` in `infra/.env`

## Reporting Outputs

The workbook is written to:

- `exports/lifescience_watch_news_latest.xlsx`
- `exports/lifescience_watch_news_YYYYMMDDTHHMMSSZ.xlsx`

The exporter uses reader-friendly views:

- `dwh.v_top_news_week_export`
- `dwh.v_top_news_month_export`
- `dwh.v_news_week_export`
- `dwh.v_news_month_export`
- `dwh.v_news_6_months_export`
- `dwh.v_news_all_export`

Workbook features:

- overview sheets for company, topic, and signal counts
- top-news tabs sorted by priority
- company-colored rows for readability
- wrapped summary text
- frozen headers and filters

## Google Drive Sync

The daily pipeline can upload the latest workbook through `rclone`.

Relevant env vars:

- `GDRIVE_UPLOAD_ENABLED`
- `GDRIVE_REMOTE`
- `GDRIVE_FOLDER`
- `GDRIVE_UPLOAD_ARCHIVE`

Typical setup:

```bash
sudo apt-get update
sudo apt-get install -y rclone
rclone config
rclone lsd gdrive-liscihub:
```

Then enable upload in `infra/.env` and run:

```bash
make refresh
```

## Important Files

- [orchestration/LS_MAIN_REFACTORED.py](/home/hl-lenovo/projects/lifescience_watch/orchestration/LS_MAIN_REFACTORED.py:1): main pipeline entrypoint
- [core/scraper.py](/home/hl-lenovo/projects/lifescience_watch/core/scraper.py:1): scrape logic
- [scripts/generate_article_summaries.py](/home/hl-lenovo/projects/lifescience_watch/scripts/generate_article_summaries.py:1): AI summary refresh
- [scripts/export_dwh_views.py](/home/hl-lenovo/projects/lifescience_watch/scripts/export_dwh_views.py:1): workbook export
- [scripts/run_daily_pipeline.sh](/home/hl-lenovo/projects/lifescience_watch/scripts/run_daily_pipeline.sh:1): scheduled end-to-end runner
- [config/scripts/dwh_views.sql](/home/hl-lenovo/projects/lifescience_watch/config/scripts/dwh_views.sql:1): reporting views
- [infra/.env.example](/home/hl-lenovo/projects/lifescience_watch/infra/.env.example:1): safe env template

## Notes

- Some sites still use anti-bot or challenge pages, so extraction quality varies by source.
- `data/*.csv` and `data/lifescience_watch.db` remain as bootstrap/local compatibility assets.
- The repo is designed to run locally on the Lenovo homelab, with VS Code over SSH as the main development workflow.
