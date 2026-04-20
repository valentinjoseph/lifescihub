# Life Science Watch

Life Science Watch is a secure news intelligence product for life-science companies. It collects articles from configured corporate sources, stores them in PostgreSQL, enriches them with AI summaries and business tags, exposes reporting views, and publishes a dashboard plus a refreshed Excel deliverable for business users.

## Executive Summary

Life Science Watch automates the end-to-end monitoring of company news across a selected life-science universe. Instead of manually visiting each corporate newsroom, the platform retrieves articles, normalizes the content, enriches it with AI-generated business summaries, and publishes the results through both a web dashboard and a scheduled spreadsheet export.

In practice, it functions as a lightweight competitive-intelligence and business-watch product:

- source monitoring is centralized in PostgreSQL configuration tables
- scraping runs automatically every day
- AI turns long-form article content into short business-readable insights
- reporting views feed both the dashboard and the Excel workbook
- the latest workbook is automatically shared through Google Drive

## Process Overview

The operational flow is intentionally simple and auditable:

1. Source URLs and run modes are read from `tech.ls_load_sources` and `tech.ls_load_config`.
2. The scraper loads company newsroom pages and article pages.
3. Cleaned article records are stored in PostgreSQL staging schemas.
4. AI generates a short summary plus structured fields such as topic, business impact, geography, and signal type.
5. DWH views assemble the reporting layer for time windows such as last 7 days, month, 6 months, and full history.
6. A formatted Excel workbook is generated from those views.
7. The workbook is uploaded to Google Drive and refreshed automatically every day at `08:00 UTC`.

## Architecture

Life Science Watch is built as a small, modular Python product:

- `Python` orchestrates scraping, summarization, export, and automation
- `PostgreSQL` stores configuration, monitoring, staging data, and summary outputs
- `FastAPI` serves the dashboard, viewer access flow, and operational endpoints
- `OpenAI` is used to transform article content into concise business-watch summaries
- `Excel export` provides a business-friendly deliverable for stakeholders
- `Google Drive` distributes the latest workbook automatically
- `Caddy` terminates HTTPS and publishes the site on its own domain

At a high level, the architecture is:

```text
Configured company sources
        ->
Python scraping pipeline
        ->
PostgreSQL staging + monitoring + summary tables
        ->
DWH reporting views
        ->
FastAPI dashboard / Excel export
        ->
Google Drive shared workbook + public website
```

For a more detailed engineering schema, see [docs/architecture/liscihub_technical_architecture.md](/home/hl-lenovo/projects/lifescience_watch/docs/architecture/liscihub_technical_architecture.md:1).

## Security Overview

The product includes a hardened security baseline designed for safe homelab hosting:

- separate `admin` and `viewer` access models
- dedicated viewer login page instead of passing viewer tokens in the URL
- secure viewer cookies with explicit lifetime
- admin-only operational endpoints for status and manual runs
- public health endpoints for safe uptime checks
- rate limiting on dashboard and chat traffic
- trusted-host enforcement for the public domain
- HTTPS published through the reverse proxy
- localhost-only app binding on the Lenovo host
- hardened container settings with dropped Linux capabilities and `no-new-privileges`
- no long-lived dashboard token persistence in browser `localStorage`

## Dashboard And Website

The website is not a separate frontend application. It is served directly by the FastAPI service:

- HTML templates render the dashboard shell and the viewer login page
- static CSS and JavaScript provide filtering, cards, and chat interactions
- dashboard data comes from PostgreSQL reporting views
- the chat experience reads the current filtered news set and returns company-level answers
- the public domain `life-science-news.com` is published through Caddy and secured with HTTPS

This makes the product easy to operate: one Python application powers the API, the dashboard, the viewer flow, and the reporting endpoints.

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

Run the local test suite:

```bash
make test
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
- `make test`: run scraper/pipeline push checks
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

- `GET /health/live`
- `GET /health/ready`
- `GET /health`
- `GET /status`
- `POST /run`
- `GET /dashboard`
- `GET /api/dashboard/news`
- `POST /api/dashboard/chat`
- `GET /viewer`
- `GET /viewer/logout`

Auth model:

- admin token: full operational access
- viewer token: read-only dashboard/news access plus chat
- public: dashboard shell and health endpoints only

Admin auth headers:

- `X-Api-Key: ${API_AUTH_TOKEN}`
- or `Authorization: Bearer ${API_AUTH_TOKEN}`
- legacy compatibility: `X-Run-Token: ${LSW_RUN_TOKEN}`

Viewer auth options:

- `X-Viewer-Token: ${VIEWER_ACCESS_TOKEN}`
- or open `/viewer` and submit the viewer token through the login form

Examples:

```bash
source infra/.env

curl http://127.0.0.1:8011/health/ready

curl http://127.0.0.1:8011/status \
  -H "X-Api-Key: ${API_AUTH_TOKEN}"

curl -X POST http://127.0.0.1:8011/run \
  -H "X-Api-Key: ${API_AUTH_TOKEN}"
```

FastAPI docs are disabled by default when `API_ENABLE_DOCS=false`.

## Dashboard

Open the local dashboard here:

```bash
http://127.0.0.1:8011/dashboard
```

What it includes:

- company dropdown with `ALL` plus only the companies that have news in the selected period
- period dropdown for `last 7 days`, `month`, `6 months`, and `all`
- filtered news cards backed by the current `dwh` export views
- a chat panel where the user can ask questions like `what are the news from the last 7 days?`
- article sources below each chat answer, including summaries and URLs, so users can verify the agent response against the original material

Viewer mode:

```bash
http://127.0.0.1:8011/viewer
```

That opens a viewer login form, sets a viewer cookie after successful sign-in, and redirects to the dashboard. The dashboard also accepts a pasted viewer or admin token in the access-token box.

## Productization Notes

This repo is now prepared for the same homelab product posture as NASAHub:

- separate admin and viewer tokens
- viewer cookie flow for shared read-only access
- public health endpoints for container and reverse-proxy checks
- rate limiting for dashboard/news/chat traffic
- trusted-host enforcement via `LISCIHUB_PUBLIC_HOST`
- hardened container settings:
  - localhost-only bind
  - `no-new-privileges`
  - all Linux capabilities dropped
  - `/tmp` isolated with `tmpfs`
  - proxy-header aware Uvicorn for reverse proxy use
  - no browser `localStorage` token persistence; dashboard access tokens stay in `sessionStorage`

To publish it on its own domain, point your Lenovo reverse proxy at:

```text
http://127.0.0.1:8011
```

Then set the public hostname in `infra/.env`:

```dotenv
LISCIHUB_PUBLIC_HOST=your-domain.example
```

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

The dashboard's `Last 7 days` period is a rolling seven-day window, not a calendar week starting on Monday.

## Priority Score

The reporting layer assigns a `priority_score` to each article so the dashboard and workbook can surface the most material items first.

This score is currently rule-based and is calculated in the SQL reporting view, not directly by the AI model. It uses the structured AI fields first, then falls back to important title keywords.

Current scoring logic:

- `95` for major signals such as `approval`, `acquisition`, `merger`, `trial-readout`, or `earnings`
- `88` for high-importance topics such as `regulatory`, `m&a`, or `financial`
- `80` for significant business events such as `partnership`, `plant-expansion`, or `launch`
- `72` for important but broader themes such as `clinical`, `partnership`, `manufacturing`, or `product`
- `84` if the article title contains `phase 3`
- `90` if the title contains `fda`
- `92` if the title contains `acquisition`
- `90` if the title contains `earnings`
- `55` by default for all other articles

Important behavior notes:

- the score is not additive; the first matching rule wins
- AI-enriched fields are evaluated before title-keyword fallbacks
- the dashboard and export views sort articles by `priority_score` descending
- top-news views use thresholds:
  - weekly top news: `priority_score >= 72`
  - monthly top news: `priority_score >= 75`

This makes the current score a practical business-importance ranking rather than a probabilistic AI confidence score.

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
