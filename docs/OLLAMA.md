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

## Benchmark And Sizing

The current local benchmark was measured with:

- model: `ollama:llama3.2:3b:bw-v3`
- CPU: Intel Core i5-8500T, 6 cores / 6 threads
- GPU: Intel UHD Graphics 630 detected, but no NVIDIA/ROCm GPU passthrough configured
- Ollama execution mode: CPU-only

Measured summary performance:

- completed Ollama summaries: 70
- elapsed window: 37 min 49.7 sec
- average speed: 32.4 sec/article
- throughput: about 111 summaries/hour

Fresh install sizing estimate:

- active configured companies/sources: 26
- current reportable article corpus: about 329 articles
- latest FULL load inserted 304 rows
- expected first FULL install volume: about 304-329 articles
- estimated Ollama summarization time for 304 articles: about 2h 44m
- estimated Ollama summarization time for 329 articles: about 2h 58m

Use this rule of thumb on similar CPU-only hardware:

```text
estimated_summary_time_seconds = article_count * 32.4
```

For example, 1,000 articles would take about 9 hours. This estimate covers Ollama summarization only; scraping and source download time depend on network and source-site response time.

## Operational Notes

The selected default model is `llama3.2:3b`, a small instruction-tuned model suitable for local summarization and chat on modest hardware. Larger models can improve quality but need more memory:

```bash
OLLAMA_MODEL=llama3.1:8b ./scripts/setup_ollama.sh
```

Keep Ollama bound to `127.0.0.1` unless you intentionally secure and expose it. The Compose file only publishes Ollama locally.
