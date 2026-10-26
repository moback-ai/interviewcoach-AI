"""LLM provider for OpenAI GPT-5.6 models on Amazon Bedrock (bedrock-mantle endpoint).

GPT-5.6 Sol/Terra/Luna are served through the OpenAI-compatible Responses API on
``bedrock-mantle.<region>.api.aws`` (NOT the bedrock-runtime Converse API used by
``common.llm.bedrock``). They are only offered in a few regions (us-east-1,
us-east-2, us-west-2), so this provider has its own region setting independent of
``BEDROCK_REGION`` (ap-south-1 in prod).

Enable with:
    LLM_PROVIDER=bedrock_mantle
    BEDROCK_CHAT_MODEL=openai.gpt-5.6-terra
    BEDROCK_MANTLE_API_KEY=<Amazon Bedrock API key>
Optional:
    BEDROCK_MANTLE_REGION=us-east-1   (default)
    BEDROCK_MANTLE_BASE_URL=...       (overrides the region-derived URL)
    LLM_REASONING_EFFORT=low          (empty string disables the reasoning parameter)
    LLM_SEND_TEMPERATURE=false        (GPT-5 reasoning models usually reject temperature)
"""
from __future__ import annotations

import time
from typing import Any, Iterator

from common.runtime_config import optional_env

DEFAULT_MODEL = "openai.gpt-5.6-terra"
DEFAULT_REGION = "us-east-1"


def _openai_client_cls():
    from openai import OpenAI

    return OpenAI


def _region() -> str:
    return (optional_env("BEDROCK_MANTLE_REGION", DEFAULT_REGION) or DEFAULT_REGION).strip()


def _base_url() -> str:
    override = (optional_env("BEDROCK_MANTLE_BASE_URL", "") or "").strip()
    if override:
        return override.rstrip("/")
    return f"https://bedrock-mantle.{_region()}.api.aws/v1"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def _max_tokens(override: int | None = None) -> int:
    """Output cap. Reasoning tokens count toward it, so keep a higher floor than Converse."""
    if override is not None:
        try:
            return max(256, min(int(override), 16384))
        except (TypeError, ValueError):
            pass
    raw = optional_env("LLM_MAX_TOKENS", "2048")
    try:
        return max(256, min(int(raw or 2048), 16384))
    except (TypeError, ValueError):
        return 2048


def _temperature(override: float | None = None) -> float:
    if override is not None:
        try:
            return max(0.0, min(float(override), 2.0))
        except (TypeError, ValueError):
            pass
    raw = optional_env("LLM_TEMPERATURE", "0.6")
    try:
        return max(0.0, min(float(raw), 2.0))
    except (TypeError, ValueError):
        return 0.6


def resolve_chat_model(model: str | None = None) -> str:
    requested = (model or "").strip()
    # Legacy/Ollama/Nova names that callers may still pass must not reach this provider.
    if requested.startswith("openai."):
        return requested
    return (optional_env("BEDROCK_CHAT_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL).strip()


def _message_text(msg: dict[str, Any]) -> str:
    content = msg.get("content")
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ).strip()
    return str(content or "").strip()


def _to_responses_input(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, str]]]:
    system_parts: list[str] = []
    items: list[dict[str, str]] = []
    for msg in messages:
        role = (msg.get("role") or "user").strip().lower()
        text = _message_text(msg)
        if not text:
            continue
        if role == "system":
            system_parts.append(text)
            continue
        if role not in ("user", "assistant"):
            role = "user"
        items.append({"role": role, "content": text})
    if not items:
        items = [{"role": "user", "content": "Hello"}]
    return "\n\n".join(system_parts), items


def _request_kwargs(
    model_id: str,
    messages: list[dict[str, Any]],
    max_tokens: int | None,
    temperature: float | None,
) -> dict[str, Any]:
    instructions, items = _to_responses_input(messages)
    kwargs: dict[str, Any] = {
        "model": model_id,
        "input": items,
        "max_output_tokens": _max_tokens(max_tokens),
    }
    if instructions:
        kwargs["instructions"] = instructions
    effort = (optional_env("LLM_REASONING_EFFORT", "low") or "").strip().lower()
    if effort:
        kwargs["reasoning"] = {"effort": effort}
    if _truthy(optional_env("LLM_SEND_TEMPERATURE", "false")):
        kwargs["temperature"] = _temperature(temperature)
    return kwargs


def _extract_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    parts: list[str] = []
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", "") != "message":
            continue
        for block in getattr(item, "content", None) or []:
            value = getattr(block, "text", None)
            if value:
                parts.append(value)
    return "".join(parts).strip()


class BedrockMantleLLMProvider:
    name = "bedrock_mantle"

    def __init__(self) -> None:
        api_key = (optional_env("BEDROCK_MANTLE_API_KEY", "") or "").strip()
        if not api_key:
            raise RuntimeError(
                "BEDROCK_MANTLE_API_KEY is required when LLM_PROVIDER=bedrock_mantle"
            )
        self._client = _openai_client_cls()(api_key=api_key, base_url=_base_url())

    def chat(
        self,
        *,
        model: str | None,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        model_id = resolve_chat_model(model)
        kwargs = _request_kwargs(model_id, messages, max_tokens, temperature)
        try:
            response = self._client.responses.create(**kwargs)
        except Exception as exc:
            raise RuntimeError(f"Bedrock mantle responses failed: {exc}") from exc
        text = _extract_text(response)
        raw_usage = getattr(response, "usage", None)
        input_tokens = int(getattr(raw_usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(raw_usage, "output_tokens", 0) or 0)
        total_tokens = int(getattr(raw_usage, "total_tokens", 0) or 0) or (
            input_tokens + output_tokens
        )
        return {
            "message": {"content": text},
            "model": model_id,
            "provider": self.name,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            },
        }

    def chat_stream(
        self,
        *,
        model: str | None,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        model_id = resolve_chat_model(model)
        kwargs = _request_kwargs(model_id, messages, max_tokens, temperature)
        try:
            stream = self._client.responses.create(stream=True, **kwargs)
        except Exception as exc:
            raise RuntimeError(f"Bedrock mantle stream failed: {exc}") from exc
        for event in stream:
            if getattr(event, "type", "") == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    yield delta

    def diagnostics(self) -> dict[str, Any]:
        model_id = resolve_chat_model()
        info = {
            "provider": self.name,
            "region": _region(),
            "model": model_id,
            "ready": False,
            "reachable": False,
            "error": "",
        }
        try:
            started = time.time()
            result = self.chat(
                model=model_id,
                messages=[{"role": "user", "content": "Reply with OK only."}],
                max_tokens=256,
            )
            if not result["message"]["content"]:
                raise RuntimeError("empty response from model")
            info["reachable"] = True
            info["ready"] = True
            info["latency_ms"] = int((time.time() - started) * 1000)
        except Exception as exc:
            info["error"] = str(exc)
        return info
