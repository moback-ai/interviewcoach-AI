from __future__ import annotations

import os
import tempfile
from typing import Any

from common.runtime_config import optional_env
from common.speech.amazon_transcribe import amazon_diagnostics, transcribe_amazon
from common.speech.local_whisper import local_whisper_diagnostics, transcribe_local_whisper
from common.speech.openrouter_whisper import openrouter_diagnostics, transcribe_openrouter
from common.transcribe_remote import transcribe_via_remote_service


def _primary_chain() -> list[str]:
    raw = optional_env("STT_PRIMARY", "openrouter").strip().lower()
    return [p.strip() for p in raw.split(",") if p.strip()]


def _fallback_chain() -> list[str]:
    raw = optional_env("STT_FALLBACK", "amazon").strip().lower()
    return [p.strip() for p in raw.split(",") if p.strip()]


def _provider_order() -> list[str]:
    order: list[str] = []
    for name in _primary_chain() + _fallback_chain():
        if name not in order:
            order.append(name)
    return order


def _transcribe_path(provider: str, wav_path: str) -> dict[str, Any]:
    if provider == "openrouter":
        return transcribe_openrouter(wav_path)
    if provider == "amazon":
        return transcribe_amazon(wav_path)
    if provider == "local_whisper":
        return transcribe_local_whisper(wav_path)
    return {"success": False, "error": f"Unknown STT provider: {provider}"}


def transcribe_audio_file(
    file_storage,
    *,
    auth_header: str | None = None,
    local_only: bool = False,
    convert_to_wav,
    is_blank_audio,
) -> dict[str, Any]:
    """Transcribe uploaded audio: OpenRouter → Amazon (prod). Legacy TRANSCRIBE_SERVICE_URL if set."""
    remote_url = (optional_env("TRANSCRIBE_SERVICE_URL", "") or "").strip()
    if remote_url and not local_only:
        return transcribe_via_remote_service(file_storage, remote_url, auth_header=auth_header)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tf:
        original = tf.name
        file_storage.save(original)

    wav_path = None
    errors: list[str] = []
    try:
        wav_path = convert_to_wav(original)
        if not wav_path:
            return {"success": False, "error": "Audio conversion failed"}
        if is_blank_audio(wav_path):
            return {"success": True, "transcription": "", "provider": "blank"}

        for provider in _provider_order():
            result = _transcribe_path(provider, wav_path)
            if result.get("success"):
                return result
            err = result.get("error") or "unknown error"
            errors.append(f"{provider}: {err}")
            print(f"[WARN] STT provider {provider} failed: {err}")

        return {
            "success": False,
            "error": "; ".join(errors) or "All STT providers failed",
        }
    finally:
        for path in (original, wav_path):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


def get_stt_diagnostics() -> dict[str, Any]:
    return {
        "chain": _provider_order(),
        "openrouter": openrouter_diagnostics(),
        "amazon": amazon_diagnostics(),
        "local_whisper": local_whisper_diagnostics(),
    }
