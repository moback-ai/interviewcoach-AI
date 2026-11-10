from unittest.mock import MagicMock, patch

import pytest

import common.runtime_config as runtime_config
from common.llm import factory
from common.llm import openrouter_provider as orp


@pytest.fixture(autouse=True)
def _openrouter_config():
    original = dict(runtime_config._CONFIG)
    runtime_config._CONFIG.update(
        {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_CHAT_MODEL": "gpt-5.6-terra",
            "LLM_PROVIDER": "openrouter",
        }
    )
    factory._PROVIDER = None
    yield
    runtime_config._CONFIG.clear()
    runtime_config._CONFIG.update(original)
    factory._PROVIDER = None


def _response(status=200, payload=None, text=""):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.json.return_value = payload or {}
    return resp


def test_factory_selects_openrouter():
    assert factory.get_provider().name == "openrouter"


def test_local_model_aliases_resolve_to_configured_model():
    assert orp.resolve_chat_model("llama3") == "gpt-5.6-terra"
    assert orp.resolve_chat_model("llama3.2:3b") == "gpt-5.6-terra"
    assert orp.resolve_chat_model(None) == "gpt-5.6-terra"
    assert orp.resolve_chat_model("openai/gpt-5") == "openai/gpt-5"


def test_chat_returns_ollama_compatible_shape():
    payload = {
        "model": "gpt-5.6-terra",
        "choices": [{"message": {"content": " hi "}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2},
    }
    with patch.object(orp.http_requests, "post", return_value=_response(payload=payload)) as post:
        out = orp.OpenRouterLLMProvider().chat(
            model="llama3",
            messages=[{"role": "user", "content": "x"}],
            max_tokens=100,
            temperature=0.3,
        )
    body = post.call_args.kwargs["json"]
    assert body["model"] == "gpt-5.6-terra"
    assert body["max_tokens"] == 100
    assert body["temperature"] == 0.3
    assert out["message"]["content"] == "hi"
    assert out["usage"] == {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}
    assert out["provider"] == "openrouter"


def test_retries_without_temperature_when_model_rejects_it():
    ok = {"choices": [{"message": {"content": "ok"}}], "usage": {}}
    rejected = _response(400, text='{"error":"temperature is not supported"}')
    with patch.object(
        orp.http_requests, "post", side_effect=[rejected, _response(payload=ok)]
    ) as post:
        out = orp.OpenRouterLLMProvider().chat(
            model=None, messages=[{"role": "user", "content": "x"}], temperature=0.3
        )
    assert out["message"]["content"] == "ok"
    assert "temperature" in post.call_args_list[0].kwargs["json"]
    assert "temperature" not in post.call_args_list[1].kwargs["json"]


def test_http_error_raises():
    with patch.object(orp.http_requests, "post", return_value=_response(500, text="boom")):
        with pytest.raises(RuntimeError, match="HTTP 500"):
            orp.OpenRouterLLMProvider().chat(
                model=None, messages=[{"role": "user", "content": "x"}]
            )


def test_missing_api_key_fails_fast():
    runtime_config._CONFIG["OPENROUTER_API_KEY"] = ""
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        orp.OpenRouterLLMProvider()
