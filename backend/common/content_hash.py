"""Content fingerprints for resume files / skills profiles and job descriptions."""
from __future__ import annotations

import hashlib
import re


_WS_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return _WS_RE.sub(" ", (value or "").strip().lower())


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_resume_bytes(file_bytes: bytes) -> str:
    return sha256_hex(file_bytes or b"")


def hash_skills_list(skills) -> str:
    parts = sorted(
        normalize_text(s)
        for s in (skills or [])
        if isinstance(s, str) and s.strip()
    )
    payload = "skills:" + ",".join(parts)
    return sha256_hex(payload.encode("utf-8"))


def hash_skills_text(skills_text: str) -> str:
    skills = [s.strip() for s in (skills_text or "").split(",") if s and s.strip()]
    return hash_skills_list(skills)


def hash_job_description(title: str, description: str) -> str:
    payload = f"{normalize_text(title)}\n{normalize_text(description)}"
    return sha256_hex(payload.encode("utf-8"))
