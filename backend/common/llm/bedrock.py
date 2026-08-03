from __future__ import annotations

import json
import time
from typing import Any, Iterator

from common.runtime_config import optional_env


def _boto3():
    import boto3

    return boto3


def _region() -> str:
    return optional_env("BEDROCK_REGION", optional_env("AWS_REGION", "ap-south-1"))


def _max_tokens(override: int | None = None) -> int:
    if override is not None:
        try:
            return max(64, min(int(override), 8192))
        except (TypeError, ValueError):
            pass
    raw = optional_env("LLM_MAX_TOKENS", optional_env("OLLAMA_NUM_PREDICT", "384"))
    try:
        return max(64, min(int(raw or 384), 8192))
    except (TypeError, ValueError):
        return 384


def _temperature(override: float | None = None) -> float:
    if override is not None:
        try:
            return max(0.0, min(float(override), 1.0))
        except (TypeError, ValueError):
            pass
    raw = optional_env("LLM_TEMPERATURE", "0.6")
    try:
        return max(0.0, min(float(raw), 1.0))
    except (TypeError, ValueError):
        return 0.6


def resolve_chat_model(model: str | None = None) -> str:
    requested = (model or "").strip()
    if requested and requested not in ("llama3", "llama3.2:3b"):
        return requested
    return optional_env(
        "BEDROCK_CHAT_MODEL",
        "apac.amazon.nova-lite-v1:0",
    ).strip() or "apac.amazon.nova-lite-v1:0"


def _message_text(msg: dict[str, Any]) -> str:
    content = msg.get("content")
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ).strip()
    return str(content or "").strip()


def _normalize_converse_messages(converse_messages: list[dict]) -> list[dict]:
    """Bedrock Converse requires user-first turns and alternating roles."""
    if not converse_messages:
        return [{"role": "user", "content": [{"text": "Hello"}]}]

    merged: list[dict] = []
    for msg in converse_messages:
        role = msg["role"]
        text = _message_text(msg)
        if not text:
            continue
        if merged and merged[-1]["role"] == role:
            prev = _message_text(merged[-1])
            merged[-1] = {
                "role": role,
                "content": [{"text": f"{prev}\n\n{text}".strip()}],
            }
        else:
            merged.append({"role": role, "content": [{"text": text}]})

    if not merged:
        return [{"role": "user", "content": [{"text": "Hello"}]}]

    # Converse rejects histories that begin with assistant (e.g. interview greeting).
    if merged[0]["role"] == "assistant":
        merged.insert(
            0,
            {
                "role": "user",
                "content": [{"text": "(Interview in progress — continue from the greeting.)"}],
            },
        )

    # Generation turns should end on a user message.
    if merged[-1]["role"] == "assistant":
        merged.append(
            {"role": "user", "content": [{"text": "Please continue."}]}
        )

    return merged


def _to_converse_messages(messages: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    system_blocks: list[dict] = []
    converse_messages: list[dict] = []
    for msg in messages:
        role = (msg.get("role") or "user").strip().lower()
        text = _message_text(msg)
        if not text:
            continue
        if role == "system":
            system_blocks.append({"text": text})
            continue
        if role not in ("user", "assistant"):
            role = "user"
        converse_messages.append(
            {"role": role, "content": [{"text": text}]}
        )
    converse_messages = _normalize_converse_messages(converse_messages)
    return system_blocks, converse_messages


class BedrockLLMProvider:
    name = "bedrock"

    def __init__(self) -> None:
        self._client = _boto3().client("bedrock-runtime", region_name=_region())

    def chat(
        self,
        *,
        model: str | None,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        model_id = resolve_chat_model(model)
        system_blocks, converse_messages = _to_converse_messages(messages)
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": converse_messages,
            "inferenceConfig": {
                "maxTokens": _max_tokens(max_tokens),
                "temperature": _temperature(temperature),
            },
        }
        if system_blocks:
            kwargs["system"] = system_blocks
        try:
            response = self._client.converse(**kwargs)
        except Exception as exc:
            raise RuntimeError(f"Bedrock converse failed: {exc}") from exc
        text = _extract_converse_text(response)
        raw_usage = response.get("usage") or {}
        usage = {
            "input_tokens": int(raw_usage.get("inputTokens") or 0),
            "output_tokens": int(raw_usage.get("outputTokens") or 0),
            "total_tokens": int(raw_usage.get("totalTokens") or 0),
        }
        if not usage["total_tokens"]:
            usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
        return {
            "message": {"content": text},
            "model": model_id,
            "provider": self.name,
            "usage": usage,
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
        system_blocks, converse_messages = _to_converse_messages(messages)
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": converse_messages,
            "inferenceConfig": {
                "maxTokens": _max_tokens(max_tokens),
                "temperature": _temperature(temperature),
            },
        }
        if system_blocks:
            kwargs["system"] = system_blocks
        try:
            stream = self._client.converse_stream(**kwargs)
        except Exception as exc:
            raise RuntimeError(f"Bedrock converse_stream failed: {exc}") from exc
        for event in stream.get("stream", []):
            delta = event.get("contentBlockDelta", {}).get("delta", {})
            text = delta.get("text")
            if text:
                yield text

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
            self.chat(
                model=model_id,
                messages=[{"role": "user", "content": "Reply with OK only."}],
            )
            info["reachable"] = True
            info["ready"] = True
            info["latency_ms"] = int((time.time() - started) * 1000)
        except Exception as exc:
            info["error"] = str(exc)
        return info


def _extract_converse_text(response: dict[str, Any]) -> str:
    output = response.get("output") or {}
    message = output.get("message") or {}
    parts = message.get("content") or []
    texts = []
    for part in parts:
        if isinstance(part, dict) and part.get("text"):
            texts.append(part["text"])
    return "".join(texts).strip()
