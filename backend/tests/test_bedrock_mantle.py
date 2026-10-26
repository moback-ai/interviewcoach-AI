import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """Read config straight from os.environ so runtime_config global state is never touched."""
    for key in (
        "BEDROCK_MANTLE_API_KEY",
        "BEDROCK_MANTLE_REGION",
        "BEDROCK_MANTLE_BASE_URL",
        "BEDROCK_CHAT_MODEL",
        "LLM_REASONING_EFFORT",
        "LLM_SEND_TEMPERATURE",
        "LLM_MAX_TOKENS",
        "LLM_PROVIDER",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BEDROCK_MANTLE_API_KEY", "test-key")
    monkeypatch.setenv("BEDROCK_CHAT_MODEL", "openai.gpt-5.6-terra")

    def fake_optional_env(name, default=""):
        return os.environ.get(name, default)

    monkeypatch.setattr("common.llm.bedrock_mantle.optional_env", fake_optional_env)
    monkeypatch.setattr("common.llm.factory.optional_env", fake_optional_env)
    yield


def _provider(client):
    from common.llm import bedrock_mantle

    with patch.object(bedrock_mantle, "_openai_client_cls") as cls:
        cls.return_value = MagicMock(return_value=client)
        provider = bedrock_mantle.BedrockMantleLLMProvider()
        return provider, cls.return_value


def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("BEDROCK_MANTLE_API_KEY")
    from common.llm.bedrock_mantle import BedrockMantleLLMProvider

    with pytest.raises(RuntimeError):
        BedrockMantleLLMProvider()


def test_base_url_uses_us_east_1_by_default():
    client = MagicMock()
    _, factory = _provider(client)
    assert factory.call_args.kwargs["base_url"] == "https://bedrock-mantle.us-east-1.api.aws/v1"
    assert factory.call_args.kwargs["api_key"] == "test-key"


def test_chat_shape_and_request():
    client = MagicMock()
    client.responses.create.return_value = SimpleNamespace(
        output_text="Hello candidate",
        usage=SimpleNamespace(input_tokens=11, output_tokens=5, total_tokens=16),
    )
    provider, _ = _provider(client)
    result = provider.chat(
        model="apac.amazon.nova-lite-v1:0",  # legacy name must map to the configured model
        messages=[
            {"role": "system", "content": "You are an interviewer."},
            {"role": "assistant", "content": "Welcome."},
            {"role": "user", "content": "Hi"},
        ],
    )
    assert result["message"]["content"] == "Hello candidate"
    assert result["model"] == "openai.gpt-5.6-terra"
    assert result["usage"] == {"input_tokens": 11, "output_tokens": 5, "total_tokens": 16}
    kwargs = client.responses.create.call_args.kwargs
    assert kwargs["model"] == "openai.gpt-5.6-terra"
    assert kwargs["instructions"] == "You are an interviewer."
    assert kwargs["input"] == [
        {"role": "assistant", "content": "Welcome."},
        {"role": "user", "content": "Hi"},
    ]
    assert kwargs["reasoning"] == {"effort": "low"}
    assert "temperature" not in kwargs
    assert kwargs["max_output_tokens"] >= 256


def test_stream_yields_text_deltas():
    client = MagicMock()
    client.responses.create.return_value = iter(
        [
            SimpleNamespace(type="response.created"),
            SimpleNamespace(type="response.output_text.delta", delta="Hel"),
            SimpleNamespace(type="response.output_text.delta", delta="lo"),
            SimpleNamespace(type="response.completed"),
        ]
    )
    provider, _ = _provider(client)
    chunks = list(provider.chat_stream(model=None, messages=[{"role": "user", "content": "Hi"}]))
    assert "".join(chunks) == "Hello"
    assert client.responses.create.call_args.kwargs["stream"] is True


def test_diagnostics_not_ready_on_error():
    client = MagicMock()
    client.responses.create.side_effect = Exception("AccessDenied")
    provider, _ = _provider(client)
    info = provider.diagnostics()
    assert info["ready"] is False
    assert "AccessDenied" in info["error"]


def test_factory_selects_mantle(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock_mantle")
    import common.llm.factory as factory

    factory._PROVIDER = None
    with patch("common.llm.bedrock_mantle._openai_client_cls"):
        assert factory.get_provider().name == "bedrock_mantle"
    factory._PROVIDER = None
