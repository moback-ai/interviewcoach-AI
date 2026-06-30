from __future__ import annotations

import os
import tempfile
import uuid
from typing import BinaryIO

import requests as http_requests

from common.runtime_config import optional_env


def _openrouter_key() -> str:
    return optional_env("OPENROUTER_API_KEY", "").strip()


def _openrouter_model() -> str:
    return optional_env("OPENROUTER_STT_MODEL", "openai/whisper-1").strip() or "openai/whisper-1"


def transcribe_openrouter(audio_path: str) -> dict:
    api_key = _openrouter_key()
    if not api_key:
        return {"success": False, "error": "OPENROUTER_API_KEY not configured", "provider": "openrouter"}

    url = optional_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    endpoint = f"{url}/audio/transcriptions"
    timeout = int(optional_env("STT_REMOTE_TIMEOUT_SECONDS", "120"))

    with open(audio_path, "rb") as handle:
        files = {"file": (os.path.basename(audio_path), handle, "application/octet-stream")}
        data = {"model": _openrouter_model()}
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": optional_env("DOMAIN", "https://ugaanlabs.ai"),
            "X-Title": "InterviewCoach",
        }
        try:
            response = http_requests.post(
                endpoint,
                headers=headers,
                files=files,
                data=data,
                timeout=timeout,
            )
        except Exception as exc:
            return {"success": False, "error": str(exc), "provider": "openrouter"}

    if response.status_code >= 400:
        return {
            "success": False,
            "error": response.text or f"OpenRouter HTTP {response.status_code}",
            "provider": "openrouter",
        }

    try:
        payload = response.json()
    except Exception:
        payload = {"text": response.text}

    text = (payload.get("text") or payload.get("transcription") or "").strip()
    return {"success": True, "transcription": text, "provider": "openrouter"}


def openrouter_diagnostics() -> dict:
    info = {
        "provider": "openrouter",
        "model": _openrouter_model(),
        "configured": bool(_openrouter_key()),
        "ready": bool(_openrouter_key()),
    }
    if not info["configured"]:
        info["error"] = "OPENROUTER_API_KEY missing"
    return info
