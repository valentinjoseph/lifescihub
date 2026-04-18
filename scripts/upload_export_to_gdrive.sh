#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="/home/hl-lenovo/projects/lifescience_watch"
EXPORT_DIR="${PROJECT_ROOT}/exports"
LATEST_FILE="${EXPORT_DIR}/lifescience_watch_news_latest.xlsx"

enabled="${GDRIVE_UPLOAD_ENABLED:-false}"
remote="${GDRIVE_REMOTE:-}"
folder="${GDRIVE_FOLDER:-LifeScienceWatch}"
upload_archive="${GDRIVE_UPLOAD_ARCHIVE:-false}"

if [[ "${enabled,,}" != "true" ]]; then
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') google drive upload disabled"
  exit 0
fi

if [[ -z "${remote}" ]]; then
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') GDRIVE_REMOTE is empty"
  exit 1
fi

if ! command -v rclone >/dev/null 2>&1; then
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') rclone is not installed"
  exit 1
fi

if ! rclone listremotes | grep -Fxq "${remote}:"; then
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') rclone remote '${remote}' is not configured"
  exit 1
fi

if [[ ! -f "${LATEST_FILE}" ]]; then
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') latest export not found at ${LATEST_FILE}"
  exit 1
fi

destination="${remote}:${folder}"

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') uploading ${LATEST_FILE} to ${destination}"
rclone copyto "${LATEST_FILE}" "${destination}/lifescience_watch_news_latest.xlsx"

if [[ "${upload_archive,,}" == "true" ]]; then
  latest_archive="$(find "${EXPORT_DIR}" -maxdepth 1 -type f -name 'lifescience_watch_news_*.xlsx' ! -name 'lifescience_watch_news_latest.xlsx' | sort | tail -n 1)"
  if [[ -n "${latest_archive}" ]]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') uploading archive $(basename "${latest_archive}") to ${destination}/archive"
    rclone copyto "${latest_archive}" "${destination}/archive/$(basename "${latest_archive}")"
  fi
fi

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') google drive upload completed"
