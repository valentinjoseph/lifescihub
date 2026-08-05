#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/infra/.env"

cd "${PROJECT_ROOT}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  source "${ENV_FILE}"
  set +a
fi

OLLAMA_MODEL_NAME="${OLLAMA_MODEL:-llama3.2:3b}"

docker compose up -d ollama

echo "Waiting for Ollama at http://127.0.0.1:${OLLAMA_PORT:-11434}"
for _ in {1..60}; do
  if curl -fsS "http://127.0.0.1:${OLLAMA_PORT:-11434}/api/tags" >/dev/null; then
    break
  fi
  sleep 2
done

curl -fsS "http://127.0.0.1:${OLLAMA_PORT:-11434}/api/tags" >/dev/null
docker exec liscihub-ollama ollama pull "${OLLAMA_MODEL_NAME}"
docker exec liscihub-ollama ollama list
