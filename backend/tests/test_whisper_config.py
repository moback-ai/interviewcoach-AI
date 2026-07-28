"""Tests for Whisper language and model configuration."""
import os
import unittest
from unittest.mock import MagicMock, patch

import common.runtime_config as runtime_config


class WhisperConfigTests(unittest.TestCase):
    def setUp(self):
        runtime_config._LOADED = False
        runtime_config._CONFIG = {}
        runtime_config._SOURCE = "unset"
        os.environ.clear()
        os.environ["RUNTIME_CONFIG_ALLOW_ENV"] = "true"

    @patch("common.speech.local_whisper.WhisperModel")
    @patch("common.speech.local_whisper.get_inference_device", return_value="cpu")
    def test_local_whisper_language_defaults_to_english(self, _mock_dev, mock_model_cls):
        mock_instance = MagicMock()
        mock_model_cls.return_value = mock_instance
        mock_instance.transcribe.return_value = ([], None)

        from common.speech.local_whisper import transcribe_local_whisper
        res = transcribe_local_whisper("dummy.wav")

        self.assertTrue(res["success"])
        mock_model_cls.assert_called_once_with("base.en", device="cpu")
        _, kwargs = mock_instance.transcribe.call_args
        self.assertEqual(kwargs.get("language"), "en")
        self.assertEqual(kwargs.get("task"), "transcribe")

    @patch("common.speech.openrouter_whisper.http_requests.post")
    def test_openrouter_whisper_sends_english_language(self, mock_post):
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "hello"}
        mock_post.return_value = mock_resp

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"dummy")
            temp_path = f.name

        try:
            from common.speech.openrouter_whisper import transcribe_openrouter
            res = transcribe_openrouter(temp_path)

            self.assertTrue(res["success"])
            self.assertEqual(res["transcription"], "hello")
            _, kwargs = mock_post.call_args
            self.assertEqual(kwargs.get("data", {}).get("language"), "en")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
