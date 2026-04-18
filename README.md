# Life Science Watch

This repo is now runnable as a normal local Python project and as an isolated Docker stack on your Lenovo homelab. It scrapes article listing pages for configured companies, fetches article pages, extracts metadata and article text, and stores the results in a local SQLite database. The compose stack also includes a dedicated PostgreSQL service for this project, wired with the same env/config conventions used in NASAHub.

## What It Does

- Reads company source URLs from `data/sources.csv`
- Reads load mode settings from `data/load_config.csv`
- Reads scraper settings from `data/scraping_config.json`
- Scrapes listing pages and article pages in parallel
- Validates and deduplicates article records by URL
- Stores company-specific results in SQLite tables
- Logs pipeline runs into a local monitoring table
- Exports the latest validated results to `outputs/latest_results.csv`
- Exposes a small API service for homelab use

## Project Layout

```text
lifescience_watch/
├── config/
├── core/
├── data/
├── db/
├── infra/
├── orchestration/
├── outputs/
├── postgres/
├── utils/
├── app.py
├── alembic.ini
└── requirements.txt
```

## Quick Start

1. Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run a dry run to validate local setup:

```bash
python -m orchestration.LS_MAIN_REFACTORED --dry-run
```

3. Run the pipeline:

```bash
python -m orchestration.LS_MAIN_REFACTORED
```

4. Start the API locally:

```bash
uvicorn app:app --host 0.0.0.0 --port 8011
```

## Homelab Setup

This project is set up to stay isolated in its own folder and compose stack. It does not depend on or modify any observability project.

### Local Lenovo Commands

Initial setup:

```bash
cd /home/hl-lenovo/projects/lifescience_watch
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
.venv/bin/python --version
alembic upgrade head
docker compose --env-file infra/.env up -d --build
```

The explicit `--env-file infra/.env` keeps this repo aligned with the NASAHub config pattern even though this compose file lives at the repo root.

Check service health:

```bash
curl http://127.0.0.1:8011/health
```

Check dedicated PostgreSQL:

```bash
docker exec -it liscihub-postgres psql -U liscihub -d liscihub -c "\dn"
```

### DBeaver Connection

Recommended option from your local machine is an SSH tunnel.

Connection settings:

- Host: `127.0.0.1`
- Port: `5434`
- Database: `liscihub`
- Username: `liscihub`
- Password: `change_me`

SSH tunnel settings:

- SSH Host: your Lenovo server
- SSH User: your normal Lenovo SSH user
- Local host after tunnel: `127.0.0.1`
- Local port after tunnel: `5434`

Schemas you should see in DBeaver:

- `tech`
- `stg_ls_pfizer`
- `stg_ls_moderna`

NASAHub-style config files in this repo:

- `infra/.env`
- `core/config.py`
- `db/session.py`
- `alembic.ini`
- `db/alembic/`
- Compose command pattern: `docker compose --env-file infra/.env ...`

Trigger a scrape run through the service:

```bash
curl -X POST http://127.0.0.1:8011/run
```

### Restart Later

If you just need to restart the app later on the Lenovo:

```bash
cd /home/hl-lenovo/projects/lifescience_watch
docker compose --env-file infra/.env restart lifescience_watch
```

If you changed code or dependencies:

```bash
cd /home/hl-lenovo/projects/lifescience_watch
docker compose --env-file infra/.env up -d --build lifescience_watch
```

## Configuration Files

`data/sources.csv`

- One row per company
- `SOURCE_1` through `SOURCE_5` hold listing-page URLs

`data/load_config.csv`

- `FULL` loads scrape everything available from the listing page
- Successful `FULL` companies are switched to `DELTA` automatically
- `DELTA` loads only keep articles newer than the company’s last successful run timestamp

`data/scraping_config.json`

- `MAX_ITEMS_PER_SOURCE`: max article links per listing page
- `MAX_WORKERS`: parallel workers
- `LISTING_SLEEP_SEC`: delay between listing requests
- `ARTICLE_SLEEP_SEC`: delay between article requests
- `REQUEST_TIMEOUT_SEC`: per-request timeout
- `MIN_TITLE_LENGTH`: validation threshold
- `EXPORT_RESULTS`: write the latest validated CSV export

## Local Storage

The pipeline uses `data/lifescience_watch.db` and creates:

- `load_monitoring`: run history and metrics
- One table per company, using normalized names derived from the company name

## Docker Service

- Postgres service: `liscihub-postgres`
- Service name: `lifescience_watch`
- Container name: `lifescience_watch`
- Restart policy: `unless-stopped`
- Exposed port: `8011`
- Postgres host port: `5434`

Port `8011` was chosen because the previous stub used `8001`, which is a common collision point on homelabs and local dev machines. Using `8011` keeps this service in a nearby, easy-to-remember range while reducing the chance of conflicting with other existing web apps.

Port `5434` is used for the dedicated PostgreSQL service so it does not collide with the existing shared PostgreSQL instance already bound on host port `5432`.

API endpoints:

- `GET /health`
- `GET /status`
- `POST /run`

PostgreSQL defaults for this stack:

- Database: `liscihub`
- Schema: `tech`
- User: `liscihub`
- Container: `liscihub-postgres`
- SQLAlchemy URL: `postgresql+psycopg://liscihub:...@localhost:5434/liscihub`

Run migrations locally:

```bash
cd /home/hl-lenovo/projects/lifescience_watch
source .venv/bin/activate
alembic upgrade head
```

## Notes

- This version no longer depends on Databricks, Spark, Delta tables, or `dbutils`.
- The shipped `data/*.csv` files are starter examples and can be replaced with your real company/source definitions.
- Some newsrooms block scraping or expose little metadata, so extraction quality will vary by source.
