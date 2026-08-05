from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from core import llm_client


class LlmClientTests(unittest.TestCase):
    def test_llm_provider_defaults_to_ollama_without_openai_key(self) -> None:
        with patch.dict(os.environ, {"LLM_PROVIDER": "", "OPENAI_API_KEY": ""}, clear=False):
            self.assertEqual(llm_client.llm_provider(), "ollama")

    def test_ollama_generate_uses_non_streaming_generate_endpoint(self) -> None:
        response = MagicMock()
        response.json.return_value = {"response": "ok"}

        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://ollama:11434"}, clear=False), patch(
            "core.llm_client.requests.post",
            return_value=response,
        ) as post:
            result = llm_client.ollama_generate("hello", "llama3.2:3b", json_mode=True)

        self.assertEqual(result, "ok")
        post.assert_called_once()
        url = post.call_args.args[0]
        payload = post.call_args.kwargs["json"]
        self.assertEqual(url, "http://ollama:11434/api/generate")
        self.assertEqual(payload["model"], "llama3.2:3b")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["format"], "json")
        response.raise_for_status.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
