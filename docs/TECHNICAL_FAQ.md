# Technical FAQ

This FAQ is a technical handover document for developers and operators maintaining this project. It focuses on runtime behavior, data flow, deployment, and common failure modes.

## Pipeline And Scraping

### What is the main pipeline entrypoint?

The scraper pipeline entrypoint is:

```bash
python -m orchestration.LS_MAIN_REFACTORED
```

The usual wrapper is:

```bash
make scrape
```

`make scrape` uses `.venv/bin/python` and runs the same module.

### What does the daily pipeline run?

The daily wrapper is `scripts/run_daily_pipeline.sh`. It runs:

```bash
python -m orchestration.LS_MAIN_REFACTORED
python scripts/generate_article_summaries.py
python scripts/purge_summarized_article_content.py
python scripts/export_dwh_views.py
./scripts/upload_export_to_gdrive.sh
```

It also sends the daily monitoring report at process exit when `DAILY_REPORT_EMAIL_ENABLED=true`.

### Where do configured sources come from?

The pipeline reads sources from PostgreSQL:

```sql
tech.ls_load_sources
```

The relevant columns are `company_name`, `source_1`, `source_2`, `source_3`, `source_4`, and `source_5`.

### Where do company load modes come from?

Load modes come from:

```sql
tech.ls_load_config
```

Rows are filtered by:

```text
flow_name = 'LS_SOURCE_SCRAPING'
active_flag = 'Y'
```

### What is the difference between FULL and DELTA?

`FULL` considers all validated articles discovered from a configured source page.

`DELTA` considers articles whose `published_date` is later than the previous successful run timestamp for the same company. It also keeps articles without a usable `published_date`, because some source sites do not expose dates reliably.

The cutoff is:

```sql
SELECT MAX(run_end_ts)
FROM tech.ls_load_monitoring
WHERE run_name = 'LS_SOURCE_SCRAPING'
  AND company_name = '<company>'
  AND run_status = 'SUCCESS';
```

### What happens to articles without a published date in DELTA mode?

They are considered eligible. In DELTA mode, known older articles are skipped, but unknown-date articles are kept because the scraper cannot prove that they are older than the previous successful run.

### Why does the scraper still fetch listing pages in DELTA mode?

The scraper must read the listing page to discover article URLs and available metadata. If the listing page contains JSON-LD dates, the scraper can skip old article pages before fetching them. If the listing page does not expose dates, the scraper may need to fetch the article page to extract the `published_date`.

### Why can a DELTA run show source errors even when no articles are loaded?

Source errors can happen before article filtering, usually while fetching a listing page. For example, a source may return `403`, `404`, a bot challenge, a redirect page, or a non-HTML response. These errors are kept in monitoring because they indicate that a source could not be checked cleanly.

### What do `attempted`, `fetched`, and `parsed` mean in the daily report?

In the monitoring report, these counts are post-DELTA eligible article counts, not every low-level HTTP request. They are intended to answer: "How many articles were considered for loading after the DELTA cutoff?"

`error_count` still records source-level scrape errors.

### Why does `records_inserted` sometimes stay at zero even when articles are parsed?

The staging tables use `url` as the primary key. If an article URL already exists, insert uses `ON CONFLICT (url) DO NOTHING`, so `records_inserted` remains zero.

## Database And Storage

### Which database is used at runtime?

Runtime storage is PostgreSQL. Connection settings come from `infra/.env`:

```dotenv
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_HOST=
POSTGRES_PORT=
```

`db/session.py` builds the SQLAlchemy URL from those variables.

### What is the purpose of the old SQLite path?

`LSW_DB_PATH` points to a legacy SQLite path used for one-time bootstrap compatibility. Runtime reads/writes use PostgreSQL.

### What are the main PostgreSQL schemas?

Core schemas:

- `tech`: configuration, monitoring, request portal, article summaries, activity logs.
- `stg_ls_<company>`: company-specific staging schemas.
- `dwh`: reporting views.
- `dea`: executive consumption views.

### How are company staging schemas named?

`db/table_manager.py` normalizes the company name into SQL-safe identifiers:

```text
Company Name -> stg_ls_company_name.stg_company_name_ingest
```

Example:

```text
PIERRE FABRE -> stg_ls_pierre_fabre.stg_pierre_fabre_ingest
```

### What columns exist in staging tables?

Each company staging table contains:

```text
id
url
title
article_content
published_date
s_created_ts
```

`article_content` is temporary processing data. The daily workflow purges it after a non-empty summary exists in `tech.ls_article_summary`, leaving the URL, title, dates, content hash, and summary fields for reporting.

The `url` column is the primary key.

### Where are successful runs recorded?

Runs are recorded in:

```sql
tech.ls_load_monitoring
```

This table stores `run_id`, `company_name`, `load_type`, `run_status`, `records_inserted`, metrics, and timestamps.

### How do I check the latest monitoring rows?

```sql
SELECT company_name, run_status, load_type, records_inserted,
       urls_attempted, urls_fetched, parse_success_count, error_count,
       run_end_ts
FROM tech.ls_load_monitoring
ORDER BY run_end_ts DESC, company_name
LIMIT 50;
```

## DWH And Reporting Views

### How is `dwh.v_news_all` built?

`dwh.v_news_all` reads from `dwh.f_news_staging_articles()`.

That function discovers staging tables dynamically from PostgreSQL metadata:

```sql
FROM pg_tables
WHERE schemaname LIKE 'stg_ls_%'
  AND tablename LIKE 'stg_%_ingest'
```

This prevents the view from needing hardcoded company names.

### Do new company staging schemas automatically appear in `v_news_all`?

Yes, after the staging schema/table exists and the DWH SQL has been applied. The function discovers matching `stg_ls_*` schemas dynamically.

### When should I run `make db-views`?

Run it after:

- changing `config/scripts/dwh_views.sql`
- creating a new database
- restoring a database
- adding DWH/DEA view changes

It is safe to rerun.

### Which views feed the dashboard?

`core/dashboard.py` maps dashboard periods to export views:

```text
week     -> dwh.v_news_week_export
month    -> dwh.v_news_month_export
6_months -> dwh.v_news_6_months_export
all      -> dwh.v_news_all_export
```

### What is the priority score?

`priority_score` is rule-based SQL logic in `config/scripts/dwh_views.sql`. It uses structured summary fields first, then title-keyword fallbacks. It is a business-importance ranking, not an AI confidence score.

## Summaries And AI

### Where are article summaries stored?

Article summaries are stored in:

```sql
tech.ls_article_summary
```

The table contains summary text, structured fields, content hash, model metadata, status, and timestamp.

### What script generates summaries?

```bash
python scripts/generate_article_summaries.py
```

or:

```bash
make summarize
```

### What happens if `OPENAI_API_KEY` is missing?

The summarizer uses a fallback extractive summary and rule-based classification. It still writes summary rows, but `summary_model` and `summary_status` identify that fallback behavior.

### When are summaries refreshed?

Summaries are refreshed when:

- the article has no existing summary
- the article content hash changed
- the target model or prompt version changed
- an existing fallback summary should be upgraded to AI

After summaries are refreshed, `scripts/purge_summarized_article_content.py` removes full article bodies from staging tables for all summarized articles. If a summary needs to be regenerated after purge, the article must be fetched again from its source URL.

## Excel Export And Google Drive

### What script creates the Excel workbook?

```bash
python scripts/export_dwh_views.py
```

or:

```bash
make export
```

### Where are workbooks written?

By default:

```text
exports/lifescience_watch_news_latest.xlsx
exports/lifescience_watch_news_YYYYMMDDTHHMMSSZ.xlsx
```

### Which database objects are exported?

The exporter reads DWH views such as:

- `dwh.v_top_news_week_export`
- `dwh.v_top_news_month_export`
- `dwh.v_news_week_export`
- `dwh.v_news_month_export`
- `dwh.v_news_6_months_export`
- `dwh.v_news_all_export`

It also exports DEA views such as:

- `dea.v_kpi_overview`
- `dea.v_company_intelligence`
- `dea.v_topic_signal_heatmap`
- `dea.v_executive_news_feed`

### How is Google Drive upload controlled?

Google Drive upload is controlled by:

```dotenv
GDRIVE_UPLOAD_ENABLED=
GDRIVE_REMOTE=
GDRIVE_FOLDER=
GDRIVE_UPLOAD_ARCHIVE=
```

The upload script is `scripts/upload_export_to_gdrive.sh` and uses `rclone`.

## Daily Monitoring Email

### What sends the monitoring email?

`scripts/run_daily_pipeline.sh` calls `scripts/send_daily_monitoring_report.py` through a shell `EXIT` trap.

### What statuses can the report show?

The report can show:

- `SUCCESS`: full daily script completed.
- `FAILED`: the daily script exited before completion.
- `SKIPPED`: another daily run was already active and the lock could not be acquired.

### What data does the email report use?

It reads rows from:

```sql
tech.ls_load_monitoring
```

for the configured report day and timezone.

### How are inserted and error rows highlighted?

The HTML report highlights:

- rows with `errors > 0` in red
- rows with `inserted > 0` in green

If both conditions are true, red takes priority.

### What SMTP configuration is required?

The sender configuration is:

```dotenv
DAILY_REPORT_EMAIL_ENABLED=true
DAILY_REPORT_EMAIL_FROM=
DAILY_REPORT_EMAIL_TO=
DAILY_REPORT_SMTP_HOST=
DAILY_REPORT_SMTP_PORT=587
DAILY_REPORT_SMTP_USERNAME=
DAILY_REPORT_SMTP_PASSWORD=
DAILY_REPORT_SMTP_STARTTLS=true
DAILY_REPORT_SMTP_SSL=false
```

For Gmail, use an app password and `smtp.gmail.com`.

## Web App, Dashboard, And API

### What framework serves the web app?

The web app is FastAPI, defined in `app.py`.

It serves:

- health endpoints
- operational endpoints
- dashboard HTML
- viewer login
- request portal
- dashboard API endpoints
- chat endpoint

### Are FastAPI docs enabled?

Docs are controlled by:

```dotenv
API_ENABLE_DOCS=false
```

When false, `/docs`, `/redoc`, and `/openapi.json` are disabled.

### What are the health endpoints?

```text
GET /health/live
GET /health/ready
GET /health
```

`/health/ready` checks database reachability.

### How is dashboard data queried?

Dashboard data is read from DWH export views in `core/dashboard.py`. Filters are applied at SQL query time for company, period, and topic.

### How does chat work?

`core/dashboard.py` fetches recent articles and either:

- calls OpenAI when `OPENAI_API_KEY` is configured
- returns a deterministic fallback answer when OpenAI is unavailable

The chat response includes source article metadata.

## Authentication And Security

### What admin auth headers are supported?

Admin endpoints accept:

```text
X-Api-Key: <API_AUTH_TOKEN>
Authorization: Bearer <API_AUTH_TOKEN>
X-Run-Token: <LSW_RUN_TOKEN>
```

`X-Run-Token` is kept for legacy compatibility.

### How does viewer auth work?

Viewer access supports:

- `X-Viewer-Token`
- a viewer cookie set after `/viewer` login
- viewer username/password credentials
- optional multi-account mapping through `VIEWER_ACCOUNTS`

### Are passwords stored as plaintext?

The auth helpers support SHA-256 password hashes using the `sha256:<hash>` format. Plain text is also supported for compatibility, but hashes are preferred.

### What does Trusted Host middleware use?

Allowed hosts are built from:

```dotenv
LISCIHUB_PUBLIC_HOST=
LISCIHUB_ALLOWED_HOSTS=
```

plus localhost defaults.

### What rate limits exist?

Rate limiting is controlled by:

```dotenv
RATE_LIMIT_ENABLED=
PUBLIC_RATE_LIMIT_WINDOW_SECONDS=
PUBLIC_RATE_LIMIT_MAX_REQUESTS=
CHAT_RATE_LIMIT_MAX_REQUESTS=
```

The limiter is in-memory and local to the running app process.

## Request Portal And Activity Monitoring

### What does the request portal do?

The request portal lets guest users submit company/source requests and lets admins approve or reject them.

Approved requests update:

```sql
tech.ls_load_sources
tech.ls_load_config
```

### Where is portal auth configured?

```dotenv
REQUEST_GUEST_USERNAME=
REQUEST_GUEST_PASSWORD=
REQUEST_ADMIN_USERNAME=
REQUEST_ADMIN_PASSWORD=
REQUEST_SESSION_SECRET=
```

### Where is dashboard activity stored?

Activity is recorded in:

```sql
tech.ls_hub_activity_monitoring
```

It tracks login, filtering, and AI chat activity for the activity-monitoring page.

## Docker And Local Operations

### What services are defined in Docker Compose?

`docker-compose.yml` defines:

- `liscihub-postgres`: PostgreSQL 16
- `lifescience_watch`: FastAPI app and Python runtime

### What ports are used by default?

Defaults:

```text
PostgreSQL host port: 5434
App host port: 8011
```

The app binds to `127.0.0.1` by default.

### How do I start the stack?

```bash
make docker-up
```

### How do I rebuild the app container?

```bash
make docker-rebuild
```

### How do I open psql?

```bash
make psql
```

### Why does the app container use `POSTGRES_HOST=liscihub-postgres`?

Inside Docker Compose, services resolve each other by service/container DNS name. The host machine uses `localhost`, but the app container uses the Compose service name.

## CI, Packages, And Deployment

### When does GitHub publish the container package?

`.github/workflows/publish-container.yml` runs on pushes to the `prod` branch and on manual workflow dispatch.

### What image tags are published?

The workflow publishes:

- `prod`
- `latest`
- `prod-<sha>`

### Does the GitHub package build download the previous package?

No. The workflow checks out the current repo and builds from source using `docker/build-push-action`. It does not define `cache-from` or pull the previous app image.

### What do GitHub package download counts mean?

They are image pull counts. They usually come from deployment hosts, `docker compose pull`, Watchtower, Portainer, manual pulls, or other Docker clients. They are not PR counts or build counts.

## Testing And Validation

### How do I run the test suite?

```bash
make test
```

or:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

### What do the tests cover?

Tests cover:

- auth helper behavior
- dashboard filters and chat behavior
- scraper extraction
- pipeline push and DELTA logic
- dynamic DWH view SQL
- table manager merge behavior
- daily monitoring report formatting

### How do I validate DWH SQL behavior without a database?

`tests/test_dwh_views_sql.py` checks that `dwh.v_news_all` uses dynamic staging discovery and does not regress to hardcoded company schemas.

### How do I validate email formatting without sending email?

`tests/test_daily_monitoring_report.py` validates plain-text and HTML report formatting without SMTP calls.

## Troubleshooting

### The dashboard is empty. What should I check?

Check, in order:

```bash
make scrape
make summarize
make db-views
make health
```

Then inspect:

```sql
SELECT COUNT(*) FROM dwh.v_news_all;
SELECT COUNT(*) FROM tech.ls_article_summary;
```

### A new company does not appear in the dashboard. What should I check?

Verify:

- `tech.ls_load_sources` has the source URL.
- `tech.ls_load_config` has an active `LS_SOURCE_SCRAPING` row.
- the scraper created `stg_ls_<company>`.
- `make db-views` has been applied.
- `dwh.v_news_all` returns rows for that company.

### A company has source errors. Does that mean the pipeline failed?

Not necessarily. A source error means that one source URL failed or returned an invalid response. The company row can still be `SUCCESS` if processing completed and the error was captured as a metric.

### Why are there no inserted records after a successful DELTA run?

That usually means no discovered dated article had `published_date > last_success_run_end_ts`, all eligible URLs already existed in the staging table, or unknown-date articles were parsed but already existed by URL.

### Why does the report show no monitoring rows?

If the daily report shows no rows, the scraper likely failed before writing to `tech.ls_load_monitoring`, or the report timezone/day does not match the rows' `run_end_ts`.

### How do I check the latest pipeline run ID?

```sql
SELECT run_id, MAX(run_end_ts) AS run_end_ts
FROM tech.ls_load_monitoring
GROUP BY run_id
ORDER BY run_end_ts DESC
LIMIT 5;
```

### How do I inspect a specific run?

```sql
SELECT company_name, run_status, load_type,
       urls_attempted, urls_fetched, parse_success_count,
       records_inserted, error_count, run_message
FROM tech.ls_load_monitoring
WHERE run_id = '<run-id>'
ORDER BY company_name;
```

### What files should not be committed?

Do not commit:

- `infra/.env`
- `docker-data/`
- `.venv/`
- generated files under `outputs/`
- generated workbooks under `exports/`
- `data/*.db`
- local logs and caches
