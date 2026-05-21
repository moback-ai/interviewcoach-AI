"""Optional forward of audio transcription to a dedicated host (e.g. AI EC2)."""
from __future__ import annotations

import os
import tempfile

import requests as http_requests

from common.runtime_config import optional_env


def transcribe_via_remote_service(file_storage, base_url: str, auth_header: str | None = None):
    base = base_url.rstrip("/")
    url = f"{base}/api/internal/transcribe-audio"
    headers = {}
    token = (optional_env("TRANSCRIBE_INTERNAL_TOKEN", "") or "").strip()
    if token:
        headers["X-Internal-Token"] = token
    if auth_header:
        headers["Authorization"] = auth_header

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tf:
        file_storage.save(tf.name)
        temp_path = tf.name

    try:
        with open(temp_path, "rb") as handle:
            response = http_requests.post(
                url,
                files={"audio": (file_storage.filename or "audio.webm", handle, file_storage.mimetype or "audio/webm")},
                headers=headers,
                timeout=int(optional_env("TRANSCRIBE_REMOTE_TIMEOUT_SECONDS", "120")),
            )
        if response.status_code >= 400:
            try:
                payload = response.json()
                message = payload.get("message") or payload.get("error") or response.text
            except Exception:
                message = response.text
            return {"success": False, "error": message or f"Remote transcribe HTTP {response.status_code}"}
        payload = response.json()
        if not payload.get("success"):
            return {"success": False, "error": payload.get("message") or "Remote transcribe failed"}
        return {"success": True, "transcription": payload.get("transcription", "")}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
