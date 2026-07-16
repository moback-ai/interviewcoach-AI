from __future__ import annotations

from typing import Any, Iterator

from common.llm.base import LLMProvider
from common.llm.ollama_provider import OllamaLLMProvider
from common.runtime_config import optional_env

_PROVIDER: LLMProvider | None = None


def _configured_provider() -> str:
    return optional_env("LLM_PROVIDER", "bedrock").strip().lower() or "bedrock"


def get_provider() -> LLMProvider:
    global _PROVIDER
    if _PROVIDER is not None:
        return _PROVIDER
    name = _configured_provider()
    if name == "ollama":
        _PROVIDER = OllamaLLMProvider()
    elif name == "bedrock":
        from common.llm.bedrock import BedrockLLMProvider

        _PROVIDER = BedrockLLMProvider()
    else:
        raise RuntimeError(f"Unsupported LLM_PROVIDER: {name}")
    return _PROVIDER


def provider_name() -> str:
    return get_provider().name


def chat(
    *,
    model: str | None,
    messages: list[dict[str, Any]],
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    return get_provider().chat(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def chat_stream(*, model: str | None, messages: list[dict[str, Any]]) -> Iterator[str]:
    yield from get_provider().chat_stream(model=model, messages=messages)


def get_llm_diagnostics() -> dict[str, Any]:
    return get_provider().diagnostics()
