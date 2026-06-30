"""Tests for PROD provider wiring (no live AWS/OpenRouter calls)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import common.runtime_config as runtime_config


class ProdProviderTests(unittest.TestCase):
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

    def test_stt_chain_prod_defaults(self):
        os.environ["STT_PRIMARY"] = "openrouter"
        os.environ["STT_FALLBACK"] = "amazon"
        runtime_config._LOADED = False
        from common.speech.factory import _provider_order

        self.assertEqual(_provider_order(), ["openrouter", "amazon"])

    def test_llm_provider_bedrock_default(self):
        os.environ["LLM_PROVIDER"] = "bedrock"
        runtime_config._LOADED = False
        from common.llm.factory import _configured_provider

        self.assertEqual(_configured_provider(), "bedrock")

    @patch("common.llm.bedrock._boto3")
    def test_bedrock_chat_shape(self, mock_boto):
        client = MagicMock()
        mock_boto.return_value.client.return_value = client
        client.converse.return_value = {
            "output": {"message": {"content": [{"text": "Hello candidate"}]}}
        }
        from common.llm.bedrock import BedrockLLMProvider

        result = BedrockLLMProvider().chat(
            model="apac.amazon.nova-lite-v1:0",
            messages=[{"role": "user", "content": "Hi"}],
        )
        self.assertEqual(result["message"]["content"], "Hello candidate")

    def test_storage_backend_flag(self):
        os.environ["STORAGE_BACKEND"] = "s3"
        os.environ["S3_BUCKET"] = "test-bucket"
        runtime_config._LOADED = False
        from common.storage_s3 import use_s3_storage

        self.assertTrue(use_s3_storage())

    def test_prod_requires_secret_id_without_allow_env(self):
        runtime_config._LOADED = False
        os.environ.pop("RUNTIME_CONFIG_ALLOW_ENV", None)
        with self.assertRaises(RuntimeError):
            runtime_config.load_runtime_config()

    @patch("common.runtime_config._fetch_secrets")
    def test_secrets_mode_ignores_env_overrides(self, mock_fetch):
        runtime_config._LOADED = False
        os.environ.pop("RUNTIME_CONFIG_ALLOW_ENV", None)
        os.environ["AWS_SECRETS_MANAGER_SECRET_ID"] = "interviewcoach/prod/app"
        os.environ["JWT_SECRET"] = "from-env-should-not-win"
        mock_fetch.return_value = {"JWT_SECRET": "from-secrets"}
        runtime_config.load_runtime_config()
        self.assertEqual(runtime_config.config_source(), "secrets_manager")
        self.assertEqual(runtime_config.optional_env("JWT_SECRET"), "from-secrets")


if __name__ == "__main__":
    unittest.main()
