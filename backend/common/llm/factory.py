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
    elif name == "openrouter":
        from common.llm.openrouter_provider import OpenRouterLLMProvider

        _PROVIDER = OpenRouterLLMProvider()
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
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    provider = get_provider()
    extra: dict[str, Any] = {}
    if reasoning_effort and getattr(provider, "name", "") == "openrouter":
        extra["reasoning_effort"] = reasoning_effort
    return provider.chat(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        **extra,
    )


def chat_stream(
    *,
    model: str | None,
    messages: list[dict[str, Any]],
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> Iterator[str]:
    yield from get_provider().chat_stream(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def get_llm_diagnostics() -> dict[str, Any]:
    return get_provider().diagnostics()
