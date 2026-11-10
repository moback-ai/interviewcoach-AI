"""Prod /api/health response shape (no live providers)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import common.runtime_config as runtime_config


class ProdHealthTests(unittest.TestCase):
    def setUp(self):
        runtime_config._LOADED = True
        runtime_config._CONFIG = {
            "JWT_SECRET": "test-secret-minimum-sixty-four-characters-long-value",
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "5432",
            "DB_NAME": "interview_db",
            "DB_USER": "u",
            "DB_PASSWORD": "p",
            "STORAGE_PATH": "/tmp/ic-test-storage",
            "LLM_PROVIDER": "bedrock",
            "BEDROCK_CHAT_MODEL": "apac.amazon.nova-lite-v1:0",
            "DOMAIN": "https://www.ugaanlabs.ai",
            "API_FAILURES_LOG_FILE": "/tmp/ic-test-api-failures.log",
        }
        runtime_config._SOURCE = "environment"
        os.environ.clear()
        os.environ["RUNTIME_CONFIG_ALLOW_ENV"] = "true"

    @patch("common.health._redis_ready", return_value=(True, ""))
    @patch("common.health._db_ready", return_value=(True, ""))
    @patch("common.speech.factory.get_stt_diagnostics")
    @patch("common.llm.factory.get_llm_diagnostics")
    def test_health_bedrock_omits_ollama_block(self, mock_llm, mock_stt, *_mocks):
        mock_llm.return_value = {
            "ready": True,
            "reachable": True,
            "model": "apac.amazon.nova-lite-v1:0",
            "model_available": True,
            "error": "",
        }
        mock_stt.return_value = {
            "chain": ["openrouter", "amazon"],
            "openrouter": {"ready": True, "provider": "openrouter"},
            "amazon": {"ready": True, "provider": "amazon"},
        }

        import app as app_module

        app_module.app.config["TESTING"] = True
        client = app_module.app.test_client()
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "healthy")
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["services"]["llm"]["provider"], "bedrock")
        self.assertNotIn("ollama", payload["services"])
        self.assertNotIn("local_whisper", payload["services"].get("stt", {}))

    @patch("common.health._redis_ready", return_value=(True, ""))
    @patch("common.health._db_ready", return_value=(True, ""))
    @patch("common.speech.factory.get_stt_diagnostics")
    @patch("common.llm.factory.get_llm_diagnostics")
    def test_health_live_and_ready(self, mock_llm, mock_stt, *_mocks):
        mock_llm.return_value = {
            "ready": True,
            "reachable": True,
            "model": "apac.amazon.nova-lite-v1:0",
            "model_available": True,
            "error": "",
        }
        mock_stt.return_value = {
            "chain": ["openrouter"],
            "openrouter": {"ready": True, "provider": "openrouter"},
        }

        import app as app_module

        app_module.app.config["TESTING"] = True
        client = app_module.app.test_client()

        live = client.get("/api/health/live")
        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.get_json()["status"], "alive")

        ready = client.get("/api/health/ready")
        self.assertEqual(ready.status_code, 200)
        self.assertTrue(ready.get_json()["ready"])

    @patch("common.health._redis_ready", return_value=(True, ""))
    @patch("common.health._db_ready", return_value=(False, "connection refused"))
    @patch("common.speech.factory.get_stt_diagnostics")
    @patch("common.llm.factory.get_llm_diagnostics")
    def test_health_ready_returns_503_when_database_down(self, mock_llm, mock_stt, *_mocks):
        mock_llm.return_value = {"ready": True, "reachable": True, "model_available": True, "error": ""}
        mock_stt.return_value = {
            "chain": ["openrouter"],
            "openrouter": {"ready": True, "provider": "openrouter"},
        }

        import app as app_module

        app_module.app.config["TESTING"] = True
        client = app_module.app.test_client()

        ready = client.get("/api/health/ready")
        self.assertEqual(ready.status_code, 503)
        self.assertFalse(ready.get_json()["ready"])

        summary = client.get("/api/health")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.get_json()["status"], "degraded")

    @patch("common.speech.factory.local_whisper_diagnostics")
    @patch("common.speech.factory.amazon_diagnostics")
    @patch("common.speech.factory.openrouter_diagnostics")
    def test_stt_diagnostics_only_active_chain(self, mock_or, mock_amz, mock_local):
        mock_or.return_value = {"provider": "openrouter", "ready": True}
        mock_amz.return_value = {"provider": "amazon", "ready": True}
        mock_local.return_value = {"provider": "local_whisper", "ready": False}
        runtime_config._CONFIG["STT_PRIMARY"] = "openrouter"
        runtime_config._CONFIG["STT_FALLBACK"] = "amazon"

        from common.speech.factory import get_stt_diagnostics

        diag = get_stt_diagnostics()
        self.assertEqual(diag["chain"], ["openrouter", "amazon"])
        self.assertIn("openrouter", diag)
        self.assertIn("amazon", diag)
        self.assertNotIn("local_whisper", diag)
        mock_local.assert_not_called()


if __name__ == "__main__":
    unittest.main()
