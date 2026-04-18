#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="/home/hl-lenovo/projects/lifescience_watch"
LOG_DIR="${PROJECT_ROOT}/outputs"
LOCK_FILE="${PROJECT_ROOT}/outputs/run_daily_pipeline.lock"

mkdir -p "${LOG_DIR}"

cd "${PROJECT_ROOT}"

set -a
source "${PROJECT_ROOT}/infra/.env"
set +a

source "${PROJECT_ROOT}/.venv/bin/activate"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') pipeline already running, exiting"
  exit 0
fi

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') starting lifescience_watch daily pipeline"
python -m orchestration.LS_MAIN_REFACTORED
python scripts/generate_article_summaries.py
python scripts/export_dwh_views.py
./scripts/upload_export_to_gdrive.sh
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') completed lifescience_watch daily pipeline"
