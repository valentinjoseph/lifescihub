#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/outputs"
LOCK_FILE="${PROJECT_ROOT}/outputs/run_daily_pipeline.lock"
RUN_STARTED_AT="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
RUN_DAILY_STATUS="FAILED"

mkdir -p "${LOG_DIR}"

cd "${PROJECT_ROOT}"

set -a
source "${PROJECT_ROOT}/infra/.env"
set +a

send_daily_monitoring_report() {
  local exit_code="$1"
  local ended_at
  ended_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

  if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    "${PROJECT_ROOT}/.venv/bin/python" "${PROJECT_ROOT}/scripts/send_daily_monitoring_report.py" \
      --pipeline-status "${RUN_DAILY_STATUS}" \
      --exit-code "${exit_code}" \
      --started-at "${RUN_STARTED_AT}" \
      --ended-at "${ended_at}" || true
  fi
}

trap 'send_daily_monitoring_report "$?"' EXIT

if [[ ! -f "${PROJECT_ROOT}/.venv/bin/activate" ]]; then
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') virtualenv not found at ${PROJECT_ROOT}/.venv"
  echo "Run 'make setup' from ${PROJECT_ROOT} first."
  exit 1
fi

source "${PROJECT_ROOT}/.venv/bin/activate"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  RUN_DAILY_STATUS="SKIPPED"
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') pipeline already running, exiting"
  exit 0
fi

echo "${RUN_STARTED_AT} starting GTM Advisor daily pipeline"
python -m orchestration.LS_MAIN_REFACTORED
python scripts/generate_article_summaries.py
python scripts/export_dwh_views.py
RUN_DAILY_STATUS="SUCCESS"
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') completed GTM Advisor daily pipeline"
