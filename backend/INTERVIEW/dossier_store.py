"""Local filesystem cache for interview dossiers keyed by resume_id + jd_id."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

from common.runtime_config import require_env

_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _sanitize_id(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    safe = _SAFE_ID_RE.sub("_", text).strip("._")
    return safe or None


def _dossier_dir() -> str:
    root = require_env("STORAGE_PATH")
    path = os.path.join(root, "dossiers")
    os.makedirs(path, exist_ok=True)
    return path


def dossier_path(resume_id: str, jd_id: str) -> str | None:
    rid = _sanitize_id(resume_id)
    jid = _sanitize_id(jd_id)
    if not rid or not jid:
        return None
    return os.path.join(_dossier_dir(), f"{rid}_{jid}.json")


def load_dossier(resume_id: str, jd_id: str) -> dict | None:
    """Return cached dossier dict, or None on miss / missing ids / failed cache / read error."""
    path = dossier_path(resume_id, jd_id)
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to load dossier cache {path}: {e}")
        return None
    if not isinstance(payload, dict):
        return None
    dossier = payload.get("dossier")
    if isinstance(dossier, dict) and dossier:
        source = (dossier.get("source") or payload.get("source") or "").strip()
        if source == "llm_failed":
            print(
                f"[WARN] Ignoring cached llm_failed dossier at {path}; "
                "will rebuild via LLM"
            )
            return None
        return dossier
    # Allow legacy/plain dossier files without wrapper
    if payload.get("must_have_skills") is not None or payload.get("source"):
        if (payload.get("source") or "").strip() == "llm_failed":
            print(
                f"[WARN] Ignoring cached llm_failed dossier at {path}; "
                "will rebuild via LLM"
            )
            return None
        return payload
    return None


def save_dossier(resume_id: str, jd_id: str, dossier: dict, job_title: str = "") -> bool:
    """Persist dossier with metadata. Skips llm_failed. Returns False if ids missing or write fails."""
    if (dossier or {}).get("source") == "llm_failed":
        print("[WARN] Refusing to cache dossier with source=llm_failed")
        return False
    path = dossier_path(resume_id, jd_id)
    if not path:
        return False
    payload = {
        "resume_id": (resume_id or "").strip(),
        "jd_id": (jd_id or "").strip(),
        "job_title": (job_title or "").strip() or (dossier or {}).get("job_title") or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": (dossier or {}).get("source") or "llm",
        "dossier": dossier or {},
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[INFO] Dossier saved: {path}")
        return True
    except Exception as e:
        print(f"[WARN] Failed to save dossier cache {path}: {e}")
        return False
