from __future__ import annotations

from typing import Any, Iterator

try:
    import ollama
except Exception as ollama_import_error:
    ollama = None
    _OLLAMA_IMPORT_ERROR = ollama_import_error
else:
    _OLLAMA_IMPORT_ERROR = None

from common.runtime_config import optional_env


def resolve_ollama_model_name(model: str | None = None) -> str:
    configured = optional_env("OLLAMA_MODEL", "llama3.2:3b").strip() or "llama3.2:3b"
    requested = (model or "").strip()
    if not requested or requested == "llama3":
        return configured
    return requested


def _chat_options() -> dict[str, Any]:
    raw = optional_env("OLLAMA_NUM_PREDICT", "384")
    try:
        num_predict = max(64, min(int(raw or 384), 1024))
    except (TypeError, ValueError):
        num_predict = 384
    return {"num_predict": num_predict, "temperature": 0.6}


class OllamaLLMProvider:
    name = "ollama"

    def chat(self, *, model: str | None, messages: list[dict[str, Any]]) -> dict[str, Any]:
        if ollama is None:
            raise RuntimeError(f"Ollama unavailable: {_OLLAMA_IMPORT_ERROR}")
        resolved = resolve_ollama_model_name(model)
        return ollama.chat(
            model=resolved,
            messages=messages,
            options=_chat_options(),
        )

    def chat_stream(self, *, model: str | None, messages: list[dict[str, Any]]) -> Iterator[str]:
        if ollama is None:
            raise RuntimeError(f"Ollama unavailable: {_OLLAMA_IMPORT_ERROR}")
        resolved = resolve_ollama_model_name(model)
        for chunk in ollama.chat(
            model=resolved,
            messages=messages,
            stream=True,
            options=_chat_options(),
        ):
            part = (chunk.get("message") or {}).get("content") or ""
            if part:
                yield part

    def diagnostics(self) -> dict[str, Any]:
        import requests as http_requests

        health_url = optional_env("OLLAMA_HEALTH_URL", "http://127.0.0.1:11434/api/tags")
        configured = resolve_ollama_model_name()
        info = {
            "provider": self.name,
            "health_url": health_url,
            "model": configured,
            "ready": False,
            "reachable": False,
            "error": "",
        }
        try:
            response = http_requests.get(health_url, timeout=2)
            info["reachable"] = response.ok
            if not response.ok:
                info["error"] = f"HTTP {response.status_code}"
                return info
            payload = response.json()
            names = {
                (m.get("name") or "").split(":")[0]
                for m in payload.get("models", [])
                if isinstance(m, dict)
            }
            base = configured.split(":")[0]
            info["model_available"] = base in names
            info["ready"] = info["model_available"]
            if not info["model_available"]:
                info["error"] = f"Model {configured} not installed"
        except Exception as exc:
            info["error"] = str(exc)
        return info
