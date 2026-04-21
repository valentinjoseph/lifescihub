.DEFAULT_GOAL := help

VENV_PYTHON := .venv/bin/python
ENV_FILE := infra/.env

.PHONY: help setup install test dry-run scrape summarize db-views export sync refresh daily docker-up docker-rebuild docker-restart health status psql

help:
	@echo "Available targets:"
	@echo "  setup            Create .venv, copy env template, install dependencies"
	@echo "  install          Install dependencies into .venv"
	@echo "  test             Run the local test suite"
	@echo "  dry-run          Validate configuration and storage without scraping"
	@echo "  scrape           Run the scraping pipeline"
	@echo "  summarize        Refresh AI/article summaries"
	@echo "  db-views         Apply DWH and DEA reporting views"
	@echo "  export           Rebuild the Excel workbook"
	@echo "  sync             Upload the latest workbook to Google Drive"
	@echo "  refresh          Run summarize + export + Google Drive sync"
	@echo "  daily            Run the full daily pipeline"
	@echo "  docker-up        Start the Docker stack"
	@echo "  docker-rebuild   Rebuild and restart the app container"
	@echo "  docker-restart   Restart the app container"
	@echo "  health           Call the authenticated health endpoint"
	@echo "  status           Call the authenticated status endpoint"
	@echo "  psql             Open a psql session in liscihub-postgres"

setup:
	python3 -m venv .venv
	@test -f $(ENV_FILE) || cp infra/.env.example $(ENV_FILE)
	$(MAKE) install

install:
	$(VENV_PYTHON) -m pip install -r requirements.txt

test:
	$(VENV_PYTHON) -m unittest discover -s tests -v

dry-run:
	$(VENV_PYTHON) -m orchestration.LS_MAIN_REFACTORED --dry-run

scrape:
	$(VENV_PYTHON) -m orchestration.LS_MAIN_REFACTORED

summarize:
	set -a && source $(ENV_FILE) && set +a && $(VENV_PYTHON) scripts/generate_article_summaries.py

db-views:
	@bash -lc 'source $(ENV_FILE) && docker exec -i liscihub-postgres psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -v ON_ERROR_STOP=1' < config/scripts/dwh_views.sql

export:
	set -a && source $(ENV_FILE) && set +a && $(VENV_PYTHON) scripts/export_dwh_views.py

sync:
	set -a && source $(ENV_FILE) && set +a && ./scripts/upload_export_to_gdrive.sh

refresh:
	set -a && source $(ENV_FILE) && set +a && $(VENV_PYTHON) scripts/generate_article_summaries.py && $(VENV_PYTHON) scripts/export_dwh_views.py && ./scripts/upload_export_to_gdrive.sh

daily:
	./scripts/run_daily_pipeline.sh

docker-up:
	docker compose --env-file $(ENV_FILE) up -d --build

docker-rebuild:
	docker compose --env-file $(ENV_FILE) up -d --build lifescience_watch

docker-restart:
	docker compose --env-file $(ENV_FILE) restart lifescience_watch

health:
	@bash -lc 'source $(ENV_FILE) && curl -s "http://127.0.0.1:$${API_BIND_PORT:-8011}/health/ready"'

status:
	@bash -lc 'source $(ENV_FILE) && curl -s "http://127.0.0.1:$${API_BIND_PORT:-8011}/status" -H "X-Api-Key: $$API_AUTH_TOKEN"'

psql:
	docker exec -it liscihub-postgres psql -U liscihub -d liscihub
