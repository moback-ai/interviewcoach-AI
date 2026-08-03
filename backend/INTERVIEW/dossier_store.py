"""Interview dossier cache: Postgres only (interview_dossiers)."""
from __future__ import annotations

import json
import re

# Bump when dossier shape changes incompatibly (e.g. highlights / jd_highlights).
DOSSIER_SCHEMA_VERSION = 2

_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _sanitize_id(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    safe = _SAFE_ID_RE.sub("_", text).strip("._")
    return safe or None


def _is_failed_dossier(dossier: dict, source: str = "") -> bool:
    src = (source or (dossier or {}).get("source") or "").strip()
    return src == "llm_failed"


def _payload_schema_version(payload: dict | None, dossier: dict | None = None) -> int:
    for source in (payload, dossier):
        if not isinstance(source, dict):
            continue
        raw = source.get("schema_version")
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return 0


def _schema_version_ok(payload: dict | None = None, dossier: dict | None = None) -> bool:
    version = _payload_schema_version(payload, dossier)
    if version >= DOSSIER_SCHEMA_VERSION:
        return True
    print(
        f"[WARN] Ignoring dossier cache schema_version={version} "
        f"(need >={DOSSIER_SCHEMA_VERSION}); will rebuild via LLM"
    )
    return False


def _load_dossier_from_db(resume_id: str, jd_id: str, user_id: str | None) -> dict | None:
    if not user_id:
        return None
    try:
        from common.db import query_one

        row = query_one(
            """
            SELECT dossier, source
            FROM interview_dossiers
            WHERE user_id=%s AND resume_id=%s AND jd_id=%s
            """,
            (user_id, resume_id, jd_id),
        )
    except Exception as e:
        print(f"[WARN] Failed to load dossier from DB: {e}")
        return None
    if not row:
        return None
    dossier = row.get("dossier")
    if isinstance(dossier, str):
        try:
            dossier = json.loads(dossier)
        except Exception:
            return None
    if not isinstance(dossier, dict) or not dossier:
        return None
    source = (row.get("source") or dossier.get("source") or "").strip()
    if _is_failed_dossier(dossier, source):
        print("[WARN] Ignoring DB llm_failed dossier; will rebuild via LLM")
        return None
    if not _schema_version_ok(None, dossier):
        return None
    return dossier


def _save_dossier_to_db(
    resume_id: str,
    jd_id: str,
    dossier: dict,
    job_title: str = "",
    user_id: str | None = None,
) -> bool:
    if not user_id:
        print("[WARN] Skipping dossier DB save: user_id is required")
        return False
    try:
        from common.db import execute

        dossier = dict(dossier or {})
        dossier["schema_version"] = DOSSIER_SCHEMA_VERSION
        title = (job_title or "").strip() or dossier.get("job_title") or ""
        source = dossier.get("source") or "llm"
        dossier_json = json.dumps(dossier)
        execute(
            """
            INSERT INTO interview_dossiers (
                user_id, resume_id, jd_id, job_title, source, dossier, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, now())
            ON CONFLICT (resume_id, jd_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                job_title = EXCLUDED.job_title,
                source = EXCLUDED.source,
                dossier = EXCLUDED.dossier,
                updated_at = now()
            """,
            (user_id, resume_id, jd_id, title, source, dossier_json),
        )
        print(f"[INFO] Dossier DB upsert resume_id={resume_id} jd_id={jd_id}")
        return True
    except Exception as e:
        print(f"[WARN] Failed to save dossier to DB: {e}")
        return False


def load_dossier(resume_id: str, jd_id: str, user_id: str | None = None) -> dict | None:
    """Return dossier from Postgres, or None on miss / failed cache / read error."""
    if not _sanitize_id(resume_id) or not _sanitize_id(jd_id):
        return None
    return _load_dossier_from_db(resume_id, jd_id, user_id)


def save_dossier(
    resume_id: str,
    jd_id: str,
    dossier: dict,
    job_title: str = "",
    user_id: str | None = None,
) -> bool:
    """Persist dossier to Postgres. Skips llm_failed. Returns False if ids/user missing."""
    if _is_failed_dossier(dossier or {}):
        print("[WARN] Refusing to cache dossier with source=llm_failed")
        return False
    if not _sanitize_id(resume_id) or not _sanitize_id(jd_id):
        return False
    return _save_dossier_to_db(
        resume_id, jd_id, dossier, job_title=job_title, user_id=user_id
    )
