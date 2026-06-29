"""Prod /api/health response shape (no live providers)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import common.runtime_config as runtime_config


class ProdHealthTests(unittest.TestCase):
    def setUp(self):
        runtime_config._LOADED = False
        runtime_config._CONFIG = {}
        runtime_config._SOURCE = "unset"
        os.environ.clear()
        os.environ["RUNTIME_CONFIG_ALLOW_ENV"] = "true"
        os.environ.setdefault("JWT_SECRET", "test-secret-minimum-sixty-four-characters-long-value")
        os.environ.setdefault("DB_HOST", "127.0.0.1")
        os.environ.setdefault("DB_PORT", "5432")
        os.environ.setdefault("DB_NAME", "interview_db")
        os.environ.setdefault("DB_USER", "u")
        os.environ.setdefault("DB_PASSWORD", "p")
        os.environ.setdefault("STORAGE_PATH", "/tmp/ic-test-storage")
        os.environ["LLM_PROVIDER"] = "bedrock"
        os.environ["BEDROCK_CHAT_MODEL"] = "apac.amazon.nova-lite-v1:0"
        os.environ["DOMAIN"] = "https://www.ugaanlabs.ai"

    @patch("app.get_stt_diagnostics")
    @patch("app.get_llm_diagnostics")
    def test_health_bedrock_omits_ollama_block(self, mock_llm, mock_stt):
        mock_llm.return_value = {
            "ready": True,
            "reachable": True,
            "model": "apac.amazon.nova-lite-v1:0",
            "model_available": True,
            "error": "",
        }
        mock_stt.return_value = {"chain": ["openrouter", "amazon"]}
        runtime_config._LOADED = False

        import app as app_module

        app_module.app.config["TESTING"] = True
        client = app_module.app.test_client()
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["services"]["llm"]["provider"], "bedrock")
        self.assertNotIn("ollama", payload["services"])


if __name__ == "__main__":
    unittest.main()
