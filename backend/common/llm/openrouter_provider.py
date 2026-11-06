from __future__ import annotations

import json
import time
from typing import Any, Iterator

import requests as http_requests

from common.runtime_config import optional_env

_LOCAL_MODEL_ALIASES = ("llama3", "llama3.2:3b")


def _api_key() -> str:
    return optional_env("OPENROUTER_API_KEY", "").strip()


def _base_url() -> str:
    return optional_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip().rstrip("/")


def _timeout() -> int:
    try:
        return int(optional_env("OPENROUTER_TIMEOUT_SECONDS", "180") or 180)
    except (TypeError, ValueError):
        return 180


def resolve_chat_model(model: str | None = None) -> str:
    requested = (model or "").strip()
    if requested and requested not in _LOCAL_MODEL_ALIASES:
        return requested
    return optional_env("OPENROUTER_CHAT_MODEL", "openai/gpt-5").strip() or "openai/gpt-5"


def _max_tokens(override: int | None = None) -> int:
    raw = override if override is not None else optional_env("LLM_MAX_TOKENS", "4096")
    try:
        return max(64, int(raw or 4096))
    except (TypeError, ValueError):
        return 4096


def _temperature(override: float | None = None) -> float:
    raw = override if override is not None else optional_env("LLM_TEMPERATURE", "0.6")
    try:
        return max(0.0, min(float(raw), 2.0))
    except (TypeError, ValueError):
        return 0.6


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": optional_env("DOMAIN", "https://ugaanlabs.ai"),
        "X-Title": "InterviewCoach",
    }


def _payload(
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int | None,
    temperature: float | None,
    *,
    stream: bool = False,
    with_temperature: bool = True,
    with_reasoning: bool = True,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": m.get("role") or "user", "content": str(m.get("content") or "")}
            for m in messages
            if str(m.get("content") or "").strip()
        ],
        "max_tokens": _max_tokens(max_tokens),
        "stream": stream,
    }
    if with_temperature:
        body["temperature"] = _temperature(temperature)
    # Reasoning models spend completion tokens on hidden thinking; "low" keeps
    # answers inside the budget and latency reasonable for interactive calls.
    # Default to "low" so an unset env var cannot let thinking eat the whole output budget.
    effort = (reasoning_effort or optional_env("OPENROUTER_REASONING_EFFORT", "low") or "low").strip().lower()
    if with_reasoning and effort in ("minimal", "low", "medium", "high"):
        body["reasoning"] = {"effort": effort}
    return body


def _rejects_temperature(status: int, text: str) -> bool:
    return status == 400 and "temperature" in (text or "").lower()


def _rejects_reasoning(status: int, text: str) -> bool:
    return status == 400 and "reason" in (text or "").lower()


class OpenRouterLLMProvider:
    name = "openrouter"

    def __init__(self) -> None:
        if not _api_key():
            raise RuntimeError("OPENROUTER_API_KEY not configured")

    def _post(self, body: dict[str, Any], *, stream: bool = False):
        return http_requests.post(
            f"{_base_url()}/chat/completions",
            headers=_headers(),
            json=body,
            timeout=_timeout(),
            stream=stream,
        )

    def chat(
        self,
        *,
        model: str | None,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        resolved = resolve_chat_model(model)
        response = None
        with_temperature, with_reasoning = True, True
        for _ in range(3):
            body = _payload(
                resolved,
                messages,
                max_tokens,
                temperature,
                with_temperature=with_temperature,
                with_reasoning=with_reasoning,
                reasoning_effort=reasoning_effort,
            )
            try:
                response = self._post(body)
            except Exception as exc:
                raise RuntimeError(f"OpenRouter request failed: {exc}") from exc
            if with_temperature and _rejects_temperature(response.status_code, response.text):
                with_temperature = False
                continue
            # Some models reject a reasoning setting they do not support; retry without it
            # instead of failing the whole generation.
            if with_reasoning and _rejects_reasoning(response.status_code, response.text):
                print(f"[WARN] OpenRouter rejected the reasoning setting for {resolved}; retrying without it")
                with_reasoning = False
                continue
            break
        if response.status_code >= 400:
            raise RuntimeError(
                f"OpenRouter HTTP {response.status_code}: {(response.text or '')[:300]}"
            )
        try:
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f"OpenRouter returned non-JSON: {(response.text or '')[:200]}") from exc
        if data.get("error"):
            raise RuntimeError(f"OpenRouter error: {str(data['error'])[:300]}")
        choice = (data.get("choices") or [{}])[0]
        text = ((choice.get("message") or {}).get("content") or "").strip()
        raw_usage = data.get("usage") or {}
        inp = int(raw_usage.get("prompt_tokens") or 0)
        out = int(raw_usage.get("completion_tokens") or 0)
        return {
            "message": {"content": text},
            "model": data.get("model") or resolved,
            "provider": self.name,
            "finish_reason": choice.get("finish_reason"),
            "usage": {
                "input_tokens": inp,
                "output_tokens": out,
                "total_tokens": int(raw_usage.get("total_tokens") or (inp + out)),
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
        resolved = resolve_chat_model(model)
        response = None
        for with_temperature in (True, False):
            body = _payload(
                resolved,
                messages,
                max_tokens,
                temperature,
                stream=True,
                with_temperature=with_temperature,
            )
            try:
                response = self._post(body, stream=True)
            except Exception as exc:
                raise RuntimeError(f"OpenRouter stream failed: {exc}") from exc
            if with_temperature and _rejects_temperature(response.status_code, response.text):
                continue
            break
        if response.status_code >= 400:
            raise RuntimeError(
                f"OpenRouter HTTP {response.status_code}: {(response.text or '')[:300]}"
            )
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if chunk == "[DONE]":
                break
            try:
                delta = (json.loads(chunk).get("choices") or [{}])[0].get("delta") or {}
            except Exception:
                continue
            part = delta.get("content")
            if part:
                yield part

    def diagnostics(self) -> dict[str, Any]:
        model_id = resolve_chat_model()
        info = {
            "provider": self.name,
            "model": model_id,
            "ready": False,
            "reachable": False,
            "error": "",
        }
        try:
            started = time.time()
            self.chat(
                model=model_id,
                messages=[{"role": "user", "content": "Reply with OK only."}],
                max_tokens=64,
            )
            info["reachable"] = True
            info["ready"] = True
            info["latency_ms"] = int((time.time() - started) * 1000)
        except Exception as exc:
            info["error"] = str(exc)
        return info
