"""Bedrock provider tests — boto3 is always mocked; no AWS calls are made."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError, ReadTimeoutError

import common.runtime_config as runtime_config
from common.llm.bedrock import (
    BedrockAccessDeniedError,
    BedrockConfigError,
    BedrockLLMProvider,
    BedrockModelNotFoundError,
    BedrockThrottledError,
    BedrockTimeoutError,
    BedrockUnavailableError,
    BedrockValidationError,
    is_fatal_llm_error,
    resolve_chat_model,
)

MODEL = "in.openai.gpt-5.6-terra"


def client_error(code: str, message: str, op: str = "Converse") -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": message},
         "ResponseMetadata": {"RequestId": "req-123"}},
        op,
    )


def ok_response(text: str = "Hello candidate") -> dict:
    return {
        "output": {"message": {"content": [{"text": text}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 4, "totalTokens": 14},
    }


class BedrockTestBase(unittest.TestCase):
    def setUp(self):
        # Snapshot global config so other test modules are unaffected.
        self._saved = (runtime_config._LOADED, dict(runtime_config._CONFIG),
                       runtime_config._SOURCE, dict(os.environ))
        self.addCleanup(self._restore)
        runtime_config._LOADED = True
        runtime_config._SOURCE = "environment"
        runtime_config._CONFIG = {
            "BEDROCK_CHAT_MODEL": MODEL,
            "BEDROCK_REGION": "ap-south-1",
            "DOMAIN": "localhost:5000",
            "API_FAILURES_LOG_FILE": "/tmp/ic-test-api-failures.log",
        }
        os.environ["RUNTIME_CONFIG_ALLOW_ENV"] = "true"
        self.client = MagicMock()
        self.provider = BedrockLLMProvider(client=self.client)

    def _restore(self):
        loaded, config, source, env = self._saved
        runtime_config._LOADED, runtime_config._CONFIG, runtime_config._SOURCE = (
            loaded, config, source)
        os.environ.clear()
        os.environ.update(env)

    def set_config(self, **values):
        runtime_config._CONFIG.update({k: str(v) for k, v in values.items()})


class ModelResolutionTests(BedrockTestBase):
    def test_missing_model_raises_config_error_not_fallback(self):
        runtime_config._CONFIG.pop("BEDROCK_CHAT_MODEL")
        with self.assertRaises(BedrockConfigError):
            resolve_chat_model()
        with self.assertRaises(BedrockConfigError):
            self.provider.chat(model="llama3", messages=[{"role": "user", "content": "hi"}])
        self.client.converse.assert_not_called()

    def test_placeholder_names_resolve_to_configured_model(self):
        for alias in (None, "", "llama3", "llama3.2:3b"):
            self.assertEqual(resolve_chat_model(alias), MODEL)

    def test_explicit_model_wins(self):
        self.assertEqual(resolve_chat_model("other.model"), "other.model")


class ChatTests(BedrockTestBase):
    def test_chat_shape_usage_and_system_prompt(self):
        self.client.converse.return_value = ok_response()
        result = self.provider.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": "You are an interviewer."},
                {"role": "user", "content": "Hi"},
            ],
            temperature=0.2,
            max_tokens=200,
        )
        self.assertEqual(result["message"]["content"], "Hello candidate")
        self.assertEqual(result["model"], MODEL)
        self.assertEqual(result["usage"]["total_tokens"], 14)
        kwargs = self.client.converse.call_args.kwargs
        self.assertEqual(kwargs["modelId"], MODEL)
        self.assertEqual(kwargs["system"], [{"text": "You are an interviewer."}])
        self.assertEqual(kwargs["inferenceConfig"], {"maxTokens": 200, "temperature": 0.2})

    def test_history_is_normalized_for_converse(self):
        self.client.converse.return_value = ok_response()
        self.provider.chat(
            model=None,
            messages=[
                {"role": "assistant", "content": "Welcome!"},
                {"role": "user", "content": "Thanks"},
                {"role": "user", "content": "Ready"},
                {"role": "assistant", "content": "Question 1"},
            ],
        )
        msgs = self.client.converse.call_args.kwargs["messages"]
        self.assertEqual(msgs[0]["role"], "user")          # user-first
        self.assertEqual(msgs[-1]["role"], "user")         # no assistant prefill
        roles = [m["role"] for m in msgs]
        self.assertTrue(all(a != b for a, b in zip(roles, roles[1:], strict=False)))  # alternating

    def test_oversized_prompt_rejected_before_aws_call(self):
        self.set_config(LLM_MAX_INPUT_CHARS=1000)
        with self.assertRaises(BedrockValidationError):
            self.provider.chat(model=None, messages=[{"role": "user", "content": "x" * 5000}])
        self.client.converse.assert_not_called()


class TemperatureTests(BedrockTestBase):
    def test_auto_mode_drops_temperature_once_model_rejects_it(self):
        self.client.converse.side_effect = [
            client_error("ValidationException",
                         "temperature is not supported for this model"),
            ok_response("first"),
            ok_response("second"),
        ]
        first = self.provider.chat(model=None, messages=[{"role": "user", "content": "a"}],
                                   temperature=0.3)
        second = self.provider.chat(model=None, messages=[{"role": "user", "content": "b"}],
                                    temperature=0.3)
        self.assertEqual(first["message"]["content"], "first")
        self.assertEqual(second["message"]["content"], "second")
        calls = self.client.converse.call_args_list
        self.assertIn("temperature", calls[0].kwargs["inferenceConfig"])
        self.assertNotIn("temperature", calls[1].kwargs["inferenceConfig"])
        self.assertNotIn("temperature", calls[2].kwargs["inferenceConfig"])  # remembered

    def test_false_mode_never_sends_temperature(self):
        self.set_config(LLM_SEND_TEMPERATURE="false")
        self.client.converse.return_value = ok_response()
        self.provider.chat(model=None, messages=[{"role": "user", "content": "a"}],
                           temperature=0.3)
        self.assertNotIn("temperature", self.client.converse.call_args.kwargs["inferenceConfig"])

    def test_true_mode_does_not_retry_on_rejection(self):
        self.set_config(LLM_SEND_TEMPERATURE="true")
        self.client.converse.side_effect = client_error(
            "ValidationException", "temperature is not supported")
        with self.assertRaises(BedrockValidationError):
            self.provider.chat(model=None, messages=[{"role": "user", "content": "a"}])
        self.assertEqual(self.client.converse.call_count, 1)

    def test_unrelated_validation_error_is_not_retried(self):
        self.client.converse.side_effect = client_error(
            "ValidationException", "messages: roles must alternate")
        with self.assertRaises(BedrockValidationError):
            self.provider.chat(model=None, messages=[{"role": "user", "content": "a"}])
        self.assertEqual(self.client.converse.call_count, 1)


class ReasoningModelTests(BedrockTestBase):
    def test_effort_sent_in_converse_shape_for_openai_models(self):
        self.set_config(LLM_REASONING_EFFORT="low")
        self.client.converse.return_value = ok_response()
        self.provider.chat(model=None, messages=[{"role": "user", "content": "a"}])
        self.assertEqual(self.client.converse.call_args.kwargs["additionalModelRequestFields"],
                         {"reasoning": {"effort": "low"}})

    def test_effort_omitted_when_unset(self):
        self.client.converse.return_value = ok_response()
        self.provider.chat(model=None, messages=[{"role": "user", "content": "a"}])
        self.assertNotIn("additionalModelRequestFields", self.client.converse.call_args.kwargs)

    def test_effort_ignored_for_non_openai_model(self):
        self.set_config(LLM_REASONING_EFFORT="low")
        self.client.converse.return_value = ok_response()
        self.provider.chat(model="apac.amazon.nova-lite-v1:0",
                           messages=[{"role": "user", "content": "a"}])
        self.assertNotIn("additionalModelRequestFields", self.client.converse.call_args.kwargs)

    def test_invalid_effort_is_config_error_before_aws_call(self):
        self.set_config(LLM_REASONING_EFFORT="extreme")
        with self.assertRaises(BedrockConfigError):
            self.provider.chat(model=None, messages=[{"role": "user", "content": "a"}])
        self.client.converse.assert_not_called()

    def test_reasoning_blocks_never_reach_reply_text(self):
        self.client.converse.return_value = {
            "output": {"message": {"content": [
                {"reasoningContent": {"reasoningText": {"text": "hidden chain of thought"}}},
                {"text": "Score: 7/10"},
            ]}},
            "stopReason": "end_turn",
            "usage": {},
        }
        res = self.provider.chat(model=None, messages=[{"role": "user", "content": "a"}])
        self.assertEqual(res["message"]["content"], "Score: 7/10")

    def test_reasoning_deltas_are_not_streamed(self):
        self.client.converse_stream.return_value = {"stream": [
            {"contentBlockDelta": {"delta": {"reasoningContent": {"text": "thinking..."}}}},
            {"contentBlockDelta": {"delta": {"text": "Next question: "}}},
            {"contentBlockDelta": {"delta": {"text": "what is a pod?"}}},
            {"messageStop": {"stopReason": "end_turn"}},
        ]}
        out = "".join(self.provider.chat_stream(
            model=None, messages=[{"role": "user", "content": "x"}]))
        self.assertEqual(out, "Next question: what is a pod?")

    def test_empty_truncated_reply_logs_effort_hint(self):
        self.set_config(LLM_REASONING_EFFORT="high")
        self.client.converse.return_value = {
            "output": {"message": {"content": [
                {"reasoningContent": {"reasoningText": {"text": "long reasoning"}}}]}},
            "stopReason": "max_tokens",
            "usage": {"outputTokens": 384},
        }
        with self.assertLogs("common.llm.bedrock", level="WARNING") as logs:
            res = self.provider.chat(model=None, messages=[{"role": "user", "content": "a"}],
                                     max_tokens=384)
        self.assertEqual(res["message"]["content"], "")
        self.assertEqual(res["stop_reason"], "max_tokens")
        self.assertIn("LLM_REASONING_EFFORT", "\n".join(logs.output))

class ErrorTranslationTests(BedrockTestBase):
    def _raise(self, exc):
        self.client.converse.side_effect = exc
        with self.assertRaises(Exception) as ctx:
            self.provider.chat(model=None, messages=[{"role": "user", "content": "a"}])
        return ctx.exception

    def test_access_denied_is_typed_fatal_and_redacted(self):
        err = self._raise(client_error(
            "AccessDeniedException",
            "User: arn:aws:sts::123456789012:assumed-role/ic-api/i-0abc is not authorized "
            "to perform: bedrock:InvokeModel on resource: "
            "arn:aws:bedrock:ap-south-1:123456789012:inference-profile/x",
        ))
        self.assertIsInstance(err, BedrockAccessDeniedError)
        self.assertIsInstance(err, RuntimeError)  # backward compatible
        self.assertTrue(is_fatal_llm_error(err))
        self.assertNotIn("123456789012", str(err))
        self.assertNotIn("ic-api", str(err))
        self.assertEqual(err.request_id, "req-123")

    def test_on_demand_error_suggests_inference_profile(self):
        err = self._raise(client_error(
            "ValidationException",
            "Invocation of model ID openai.gpt-5.6-terra with on-demand throughput isn't supported."))
        self.assertIsInstance(err, BedrockValidationError)
        self.assertIn("inference profile", str(err))

    def test_mapping_of_common_codes(self):
        cases = {
            "ResourceNotFoundException": BedrockModelNotFoundError,
            "ThrottlingException": BedrockThrottledError,
            "ServiceUnavailableException": BedrockUnavailableError,
            "ModelTimeoutException": BedrockTimeoutError,
        }
        for code, cls in cases.items():
            self.client.converse.reset_mock()
            err = self._raise(client_error(code, "boom"))
            self.assertIsInstance(err, cls, code)
        self.assertTrue(BedrockThrottledError.retryable)
        self.assertFalse(is_fatal_llm_error(BedrockThrottledError("x")))

    def test_read_timeout_maps_to_timeout(self):
        err = self._raise(ReadTimeoutError(endpoint_url="https://bedrock-runtime"))
        self.assertIsInstance(err, BedrockTimeoutError)


class StreamTests(BedrockTestBase):
    def test_stream_yields_text(self):
        self.client.converse_stream.return_value = {"stream": [
            {"messageStart": {"role": "assistant"}},
            {"contentBlockDelta": {"delta": {"text": "Tell me "}}},
            {"contentBlockDelta": {"delta": {"text": "about yourself."}}},
            {"messageStop": {"stopReason": "end_turn"}},
        ]}
        out = "".join(self.provider.chat_stream(
            model=None, messages=[{"role": "user", "content": "start"}]))
        self.assertEqual(out, "Tell me about yourself.")

    def test_stream_error_event_raises_instead_of_silently_truncating(self):
        self.client.converse_stream.return_value = {"stream": [
            {"contentBlockDelta": {"delta": {"text": "Partial"}}},
            {"throttlingException": {"message": "Too many requests"}},
        ]}
        gen = self.provider.chat_stream(model=None, messages=[{"role": "user", "content": "x"}])
        self.assertEqual(next(gen), "Partial")
        with self.assertRaises(BedrockThrottledError):
            next(gen)

    def test_exception_during_iteration_is_translated(self):
        def broken():
            yield {"contentBlockDelta": {"delta": {"text": "a"}}}
            raise ReadTimeoutError(endpoint_url="https://bedrock-runtime")

        self.client.converse_stream.return_value = {"stream": broken()}
        with self.assertRaises(BedrockTimeoutError):
            list(self.provider.chat_stream(model=None,
                                           messages=[{"role": "user", "content": "x"}]))


class DiagnosticsTests(BedrockTestBase):
    def test_diagnostics_are_cached(self):
        self.client.converse.return_value = ok_response("OK")
        first = self.provider.diagnostics()
        second = self.provider.diagnostics()
        self.assertTrue(first["ready"])
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(self.client.converse.call_count, 1)
        self.provider.diagnostics(force=True)
        self.assertEqual(self.client.converse.call_count, 2)

    def test_diagnostics_failure_is_redacted_and_coded(self):
        self.client.converse.side_effect = client_error(
            "AccessDeniedException",
            "User: arn:aws:sts::123456789012:assumed-role/ic-api/x is not authorized")
        info = self.provider.diagnostics()
        self.assertFalse(info["ready"])
        self.assertTrue(info["reachable"])
        self.assertEqual(info["error_code"], "AccessDenied")
        self.assertNotIn("123456789012", info["error"])

    def test_diagnostics_reports_missing_model_without_calling_aws(self):
        runtime_config._CONFIG.pop("BEDROCK_CHAT_MODEL")
        info = self.provider.diagnostics()
        self.assertEqual(info["error_code"], "ConfigError")
        self.client.converse.assert_not_called()


class ClientConfigTests(BedrockTestBase):
    @patch("common.llm.bedrock._boto3")
    def test_client_uses_region_timeouts_and_bounded_retries(self, mock_boto):
        self.set_config(BEDROCK_MAX_ATTEMPTS=4, BEDROCK_READ_TIMEOUT_SECONDS=90)
        BedrockLLMProvider()
        _, kwargs = mock_boto.return_value.client.call_args
        cfg = kwargs["config"]
        self.assertEqual(cfg.region_name, "ap-south-1")
        self.assertEqual(cfg.read_timeout, 90)
        self.assertEqual(cfg.retries, {"mode": "standard", "max_attempts": 4})


class CallerRetryTests(BedrockTestBase):
    @patch("common.llm.factory.chat")
    def test_try_ollama_chat_stops_on_fatal_error(self, mock_chat):
        from INTERVIEW.generation_utils import try_ollama_chat

        mock_chat.side_effect = BedrockAccessDeniedError("denied")
        with self.assertRaises(BedrockAccessDeniedError):
            try_ollama_chat("prompt", max_retries=3)
        self.assertEqual(mock_chat.call_count, 1)

    @patch("common.llm.factory.chat")
    def test_try_ollama_chat_still_retries_transient_errors(self, mock_chat):
        from INTERVIEW.generation_utils import try_ollama_chat

        mock_chat.side_effect = [BedrockThrottledError("slow down"), ok_response()]
        resp = try_ollama_chat("prompt", max_retries=3)
        self.assertEqual(mock_chat.call_count, 2)
        self.assertIn("output", resp)


if __name__ == "__main__":
    unittest.main()
