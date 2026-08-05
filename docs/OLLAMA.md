# Ollama Local Model Setup

This project can use Ollama for both article summaries and dashboard chat.

## Configuration

Set these values in `infra/.env`:

```bash
LLM_PROVIDER=ollama
OLLAMA_PORT=11434
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_SUMMARY_MODEL=llama3.2:3b
OLLAMA_CHAT_MODEL=llama3.2:3b
OLLAMA_REQUEST_TIMEOUT_SEC=180
OLLAMA_NUM_PREDICT=320
SUMMARY_MAX_CONTENT_CHARS=6000
```

Inside Docker Compose, the app receives `OLLAMA_BASE_URL=http://ollama:11434` automatically.

## Install And Pull Model

From the project root:

```bash
chmod +x scripts/setup_ollama.sh
./scripts/setup_ollama.sh
docker compose up -d --build gtm_advisor
```

The setup script starts the `ollama/ollama` Docker service, waits for the local API, pulls `OLLAMA_MODEL`, and lists installed models.

## Verify

```bash
curl -fsS http://127.0.0.1:11434/api/tags
docker exec gtm_advisor python scripts/generate_article_summaries.py --limit 1
```

The summarizer purges staged `article_content` automatically after summaries are written. Use `--skip-purge` only for debugging.

## Operational Notes

The selected default model is `llama3.2:3b`, a small instruction-tuned model suitable for local summarization and chat on modest hardware. Larger models can improve quality but need more memory:

```bash
OLLAMA_MODEL=llama3.1:8b ./scripts/setup_ollama.sh
```

Keep Ollama bound to `127.0.0.1` unless you intentionally secure and expose it. The Compose file only publishes Ollama locally.
