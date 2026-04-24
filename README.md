# Life Science Watch

Life Science Watch is a secure news intelligence product for life-science companies. It collects articles from configured corporate sources, stores them in PostgreSQL, enriches them with AI summaries and business tags, exposes reporting views, and publishes a dashboard plus a refreshed Excel deliverable for business users.

## Executive Summary

Life Science Watch automates the end-to-end monitoring of company news across a selected life-science universe. Instead of manually visiting each corporate newsroom, the platform retrieves articles, normalizes the content, enriches it with AI-generated business summaries, and publishes the results through both a web dashboard and a scheduled spreadsheet export.

In practice, it functions as a lightweight competitive-intelligence and business-watch product:

- source monitoring is centralized in PostgreSQL configuration tables
- scraping runs automatically every day
- AI turns long-form article content into short business-readable insights
- DWH views feed both the dashboard and DEA consumption marts
- DEA views provide executive KPIs, company intelligence, topic/signal heatmaps, and priority news feeds
- the latest workbook is automatically shared through Google Drive

## Process Overview

The operational flow is intentionally simple and auditable:

1. Source URLs and run modes are read from `tech.ls_load_sources` and `tech.ls_load_config`.
2. The scraper loads company newsroom pages and article pages.
3. Cleaned article records are stored in PostgreSQL staging schemas.
4. AI generates a short summary plus structured fields such as topic, business impact, geography, and signal type.
5. DWH views assemble the article-level reporting layer for time windows such as last 7 days, month, 6 months, and full history.
6. DEA views assemble decision-ready consumption marts from the DWH layer.
7. A formatted Excel workbook is generated from those views.
8. The workbook is uploaded to Google Drive and refreshed automatically every day at `08:00 UTC`.

## Architecture

Life Science Watch is built as a small, modular Python product:

- `Python` orchestrates scraping, summarization, export, and automation
- `PostgreSQL` stores configuration, monitoring, staging data, and summary outputs
- `FastAPI` serves the dashboard, viewer access flow, and operational endpoints
- `OpenAI` is used to transform article content into concise business-watch summaries
- `Excel export` provides a business-friendly deliverable for stakeholders
- `Google Drive` distributes the latest workbook automatically
- an optional reverse proxy can terminate HTTPS and publish the site on your own domain

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
DEA consumption marts
        ->
FastAPI dashboard / Excel export
        ->
Google Drive shared workbook + public website
```

For a more detailed engineering schema, see [docs/architecture/liscihub_technical_architecture.md](docs/architecture/liscihub_technical_architecture.md).

## Security Overview

The product includes a hardened security baseline designed for safe homelab hosting:

- separate `admin` and `viewer` access models
- dedicated viewer login page instead of passing viewer tokens in the URL
- secure viewer cookies with explicit lifetime
- admin-only operational endpoints for status and manual runs
- public health endpoints for safe uptime checks
- rate limiting on dashboard and chat traffic
- trusted-host enforcement for the configured public domain
- HTTPS published through the reverse proxy
- localhost-only app and database bindings by default
- hardened container settings with dropped Linux capabilities and `no-new-privileges`
- no long-lived dashboard token persistence in browser `localStorage`

## Dashboard And Website

The website is not a separate frontend application. It is served directly by the FastAPI service:

- HTML templates render the dashboard shell and the viewer login page
- static CSS and JavaScript provide filtering, cards, and chat interactions
- dashboard data comes from PostgreSQL reporting views
- the news feed can be filtered independently by period, company, and topic
- the chat experience stays all-company for the selected period, regardless of the news-feed company or topic filters
- a public domain can be published through a reverse proxy by setting `LISCIHUB_PUBLIC_HOST`

This makes the product easy to operate: one Python application powers the API, the dashboard, the viewer flow, and the reporting endpoints.

## What It Does

- reads source URLs from `tech.ls_load_sources`
- reads `FULL` / `DELTA` mode from `tech.ls_load_config`
- scrapes listing pages and article pages
- stores staged articles in company-specific schemas
- generates AI summaries plus structured fields like topic and business impact
- exposes DWH views for article-level reporting
- exposes DEA views for decision-ready consumption marts
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
│   └── scripts/                DWH and DEA views plus seed SQL
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
git clone <repo-url> lifescience_watch
cd lifescience_watch
make setup
source .venv/bin/activate
```

`make setup` creates `.venv`, installs dependencies, and copies `infra/.env.example` to `infra/.env` if it does not exist. Fill in `infra/.env` before starting the stack.

Useful first checks:

```bash
make dry-run
make docker-up
make health
```

After the first successful scrape or legacy-data bootstrap, apply the reporting views:

```bash
make db-views
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
make db-views
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
- `make db-views`: create or refresh DWH and DEA SQL views in PostgreSQL
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

Portable cron example:

```cron
0 8 * * * cd /path/to/lifescience_watch && /bin/bash scripts/run_daily_pipeline.sh >> outputs/run_daily_pipeline.log 2>&1
```

The script resolves the repository root from its own location, so it does not require the project to live under a specific username or host path.

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
 - `GET /requests/login`
 - `GET /requests`
 - `GET /requests/logout`

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
- or open `/viewer` and sign in with `VIEWER_USERNAME` plus the password whose SHA-256 hash is stored in `VIEWER_PASSWORD_HASH`

Request portal auth:

- guest request account: `REQUEST_GUEST_USERNAME` / `REQUEST_GUEST_PASSWORD`
- admin review account: `REQUEST_ADMIN_USERNAME` / `REQUEST_ADMIN_PASSWORD`
- approval writes approved requests into `tech.ls_load_sources` and `tech.ls_load_config`

Examples:

```bash
source infra/.env
BASE_URL="http://127.0.0.1:${API_BIND_PORT:-8011}"

curl "${BASE_URL}/health/ready"

curl "${BASE_URL}/status" \
  -H "X-Api-Key: ${API_AUTH_TOKEN}"

curl -X POST "${BASE_URL}/run" \
  -H "X-Api-Key: ${API_AUTH_TOKEN}"

curl "${BASE_URL}/api/dashboard/news?company=ALL&period=week&topic=financial" \
  -H "X-Viewer-Token: ${VIEWER_ACCESS_TOKEN}"

curl -X POST "${BASE_URL}/api/dashboard/chat" \
  -H "Content-Type: application/json" \
  -H "X-Viewer-Token: ${VIEWER_ACCESS_TOKEN}" \
  -d '{"question":"What are the most important updates this week?","period":"week"}'
```

FastAPI docs are disabled by default when `API_ENABLE_DOCS=false`.

## Dashboard

Open the local dashboard here:

```bash
source infra/.env
echo "http://127.0.0.1:${API_BIND_PORT:-8011}/dashboard"
```

With the default `API_BIND_PORT=8011`, that is `http://127.0.0.1:8011/dashboard`.

What it includes:

- company dropdown with `ALL` plus only the companies that have news in the selected period
- period dropdown for `last 7 days`, `month`, `6 months`, and `all`
- topic dropdown with `ALL` plus available `key_topic` values such as `financial`, `clinical`, `corporate`, `manufacturing`, `m&a`, or `regulatory`
- filtered news cards backed by the current `dwh` export views; the feed applies period, company, and topic together
- a chat panel where the user can ask questions like `what are the news from the last 7 days?`
- chat answers query all companies for the selected period and do not inherit the news-feed company or topic filters
- article sources below each chat answer, including summaries and URLs, so users can verify the agent response against the original material

Viewer mode:

```bash
source infra/.env
echo "http://127.0.0.1:${API_BIND_PORT:-8011}/viewer"
```

With the default `API_BIND_PORT=8011`, that is `http://127.0.0.1:8011/viewer`.

That opens a viewer username/password login form, sets a viewer cookie after successful sign-in, and redirects to the dashboard. The dashboard also accepts a pasted viewer or admin token in the access-token box.

## Productization Notes

This repo is prepared for local development, homelab hosting, or small-server deployment:

- separate admin and viewer tokens
- viewer cookie flow for shared read-only access
- public health endpoints for container and reverse-proxy checks
- rate limiting for dashboard/news/chat traffic
- trusted-host enforcement via `LISCIHUB_PUBLIC_HOST`
- hardened container settings:
  - localhost-only bind by default
  - `no-new-privileges`
  - all Linux capabilities dropped
  - `/tmp` isolated with `tmpfs`
  - proxy-header aware Uvicorn for reverse proxy use
  - no browser `localStorage` token persistence; dashboard access tokens stay in `sessionStorage`

To publish it on your own domain, point your reverse proxy at the local app port:

```text
http://127.0.0.1:${API_BIND_PORT:-8011}
```

Use the concrete value from `infra/.env` in your proxy config, for example `http://127.0.0.1:8011` when `API_BIND_PORT=8011`.

Then set the public hostname in `infra/.env`:

```dotenv
LISCIHUB_PUBLIC_HOST=your-domain.example
```

## Database Notes

Connection defaults:

- database: `liscihub`
- schema: `tech`
- postgres container: `liscihub-postgres`
- host port: value of `POSTGRES_PORT` in `infra/.env`; default `5434`

DBeaver on the same machine:

- host: `127.0.0.1`
- port: value of `POSTGRES_PORT`; default `5434`
- database: `liscihub`
- username: `liscihub`
- password: value of `POSTGRES_PASSWORD` in `infra/.env`

DBeaver from another workstation:

- create an SSH tunnel to the deployment host that forwards your local port to `127.0.0.1:${POSTGRES_PORT:-5434}` on the host
- connect DBeaver to the local tunnel endpoint with the same database, username, and password values

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
- `dea.v_kpi_overview`
- `dea.v_company_intelligence`
- `dea.v_topic_signal_heatmap`
- `dea.v_executive_news_feed`

Workbook features:

- overview sheets for company, topic, and signal counts
- DEA sheets for executive KPIs, company intelligence, topic/signal heatmaps, and priority news feeds
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
rclone lsd <your-rclone-remote>:
```

Then enable upload in `infra/.env` and run:

```bash
make refresh
```

## Important Files

- [orchestration/LS_MAIN_REFACTORED.py](orchestration/LS_MAIN_REFACTORED.py): main pipeline entrypoint
- [core/scraper.py](core/scraper.py): scrape logic
- [scripts/generate_article_summaries.py](scripts/generate_article_summaries.py): AI summary refresh
- [scripts/export_dwh_views.py](scripts/export_dwh_views.py): workbook export
- [scripts/run_daily_pipeline.sh](scripts/run_daily_pipeline.sh): scheduled end-to-end runner
- [config/scripts/dwh_views.sql](config/scripts/dwh_views.sql): DWH reporting views and DEA consumption marts
- [infra/.env.example](infra/.env.example): safe env template

## Notes

- Some sites still use anti-bot or challenge pages, so extraction quality varies by source.
- `data/*.csv` and `data/lifescience_watch.db` remain as bootstrap/local compatibility assets.
- The repo is designed to run from any checkout path. Keep machine-specific values in `infra/.env`, cron entries, reverse-proxy config, and rclone config rather than committing them to source files.
