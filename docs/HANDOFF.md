# GTM Advisor Company Handoff Guide

This repository is ready to share as a working base for continued company development. It contains the application code, database schema assets, Docker Compose services, local Ollama configuration, dashboard templates, tests, and operational scripts.

## What To Share

Share the repository source code and documentation, including:

- `README.md`
- `docs/`
- `app.py`, `core/`, `db/`, `orchestration/`, `scripts/`, `utils/`
- `config/scripts/`
- `data/*.csv` and `data/*.json` seed/config examples
- `docker-compose.yml`, `Dockerfile`, `Makefile`, `requirements.txt`
- `infra/.env.example`

Do not share local secrets or machine-specific state:

- `infra/.env`
- PostgreSQL data volumes or `docker-data/`
- local virtual environments such as `.venv/`
- generated caches such as `__pycache__/`
- exported workbooks unless the company is allowed to receive the underlying article data

## Current Architecture

The app is multi-sector. Companies are configured with `INDUSTRY_SECTOR` in both:

```sql
tech.ls_load_sources
tech.ls_load_config
```

The scraper writes each company to:

```text
stg_<industry_sector>.stg_<company>
```

Example:

```text
ORANGE in TELECOMMUNICATION -> stg_telecommunication.stg_orange
```

The DWH and DEA views dynamically discover staging tables from PostgreSQL metadata using `STG%` schemas and `STG%` tables, so new sectors and companies do not require hardcoded DWH SQL changes once their staging tables exist.

## AI Configuration

The active AI provider is local Ollama. It is used for both:

- article summaries
- dashboard chatbot answers

Default model:

```text
llama3.2:3b
```

Relevant environment variables:

```bash
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
OLLAMA_SUMMARY_MODEL=llama3.2:3b
OLLAMA_CHAT_MODEL=llama3.2:3b
OLLAMA_NUM_PREDICT=320
SUMMARY_MAX_CONTENT_CHARS=6000
```

See [OLLAMA.md](OLLAMA.md) for the setup and verification procedure.

## First Setup On A New Machine

From the project root:

```bash
cp infra/.env.example infra/.env
make setup
chmod +x scripts/setup_ollama.sh
./scripts/setup_ollama.sh
docker compose --env-file infra/.env up -d --build
make db-views
make test
```

Then open:

```text
http://127.0.0.1:8011/dashboard
```

Adjust the port if `API_BIND_PORT` is changed in `infra/.env`.

## Operational Flow

Normal daily processing is:

```bash
make daily
```

That runs:

1. scrape configured companies
2. summarize staged article content with Ollama
3. purge full article bodies after summaries exist
4. export DWH/DEA views to Excel

Manual pieces are:

```bash
make scrape
make summarize
make db-views
make export
```

## Verification Checklist

Use these checks before handing off a build:

```bash
docker compose --env-file infra/.env ps
curl -fsS http://127.0.0.1:11434/api/tags
make test
make health
```

Database checks:

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'tech'
  AND table_name IN ('ls_load_sources', 'ls_load_config')
  AND column_name = 'industry_sector';

SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname ILIKE 'stg%'
  AND tablename ILIKE 'stg%'
ORDER BY schemaname, tablename;

SELECT industry_sector, company_name, COUNT(*) AS article_count, COUNT(article_summary) AS summarized_count
FROM dwh.v_news_all
GROUP BY industry_sector, company_name
ORDER BY industry_sector, company_name;
```

Dashboard API check:

```bash
source infra/.env
curl -fsS "http://127.0.0.1:${API_BIND_PORT:-8011}/api/dashboard/news?industry_sector=ALL&company=ALL&period=all&topic=ALL" \
  -H "X-Api-Key: ${API_AUTH_TOKEN}"
```

## Notes For Future Development

- Local Ollama inference is slower than hosted APIs on CPU. Larger backfills may take time.
- Full article content is intentionally temporary. After summaries are generated, `article_content` is purged from staging.
- To regenerate summaries after purge, rerun scraping so article content is fetched again.
- Keep DWH/DEA view discovery dynamic. Do not hardcode company or sector staging tables.
- Keep `infra/.env.example` as the public template and keep `infra/.env` private.
