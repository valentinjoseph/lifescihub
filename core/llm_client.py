"""LLM provider helpers for OpenAI and local Ollama inference."""

from __future__ import annotations

import os
from typing import Any

import requests
from openai import OpenAI


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
DEFAULT_OLLAMA_NUM_PREDICT = 320


def llm_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider:
        return provider
    return "openai" if os.getenv("OPENAI_API_KEY") else "ollama"


def openai_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=api_key) if api_key else None


def openai_model(default: str = "gpt-5-mini") -> str:
    return os.getenv("OPENAI_MODEL", default)


def ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def ollama_summary_model() -> str:
    return os.getenv("OLLAMA_SUMMARY_MODEL", os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL))


def ollama_chat_model() -> str:
    return os.getenv("OLLAMA_CHAT_MODEL", os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL))


def ollama_num_predict() -> int:
    return int(os.getenv("OLLAMA_NUM_PREDICT", str(DEFAULT_OLLAMA_NUM_PREDICT)))


def ollama_generate(
    prompt: str,
    model: str,
    *,
    json_mode: bool = False,
    timeout: int | None = None,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": ollama_num_predict()},
    }
    if json_mode:
        payload["format"] = "json"

    response = requests.post(
        f"{ollama_base_url()}/api/generate",
        json=payload,
        timeout=timeout or int(os.getenv("OLLAMA_REQUEST_TIMEOUT_SEC", "180")),
    )
    response.raise_for_status()
    data = response.json()
    return str(data.get("response") or "").strip()
