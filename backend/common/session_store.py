"""
session_store.py
Persistent interview session storage using PostgreSQL.
Replaces the in-memory `interview_instances = {}` dict in app.py.
"""
import json
import os
from common.db import query_one, execute


def _ensure_table():
    execute("""
        CREATE TABLE IF NOT EXISTS interview_sessions (
            session_key TEXT PRIMARY KEY,
            state_json  JSONB NOT NULL,
            updated_at  TIMESTAMPTZ DEFAULT now()
        )
    """)
    execute("CREATE INDEX IF NOT EXISTS idx_interview_sessions_updated ON interview_sessions(updated_at)")


_table_ready = False


def _ensure_table_once():
    global _table_ready
    if _table_ready:
        return
    _ensure_table()
    _table_ready = True


def load_session(session_key: str) -> dict | None:
    _ensure_table_once()
    row = query_one("SELECT state_json FROM interview_sessions WHERE session_key = %s", (session_key,))
    if row:
        return row["state_json"]
    return None


def save_session(session_key: str, state: dict):
    _ensure_table_once()
    execute("""
        INSERT INTO interview_sessions (session_key, state_json, updated_at)
        VALUES (%s, %s, now())
        ON CONFLICT (session_key) DO UPDATE
            SET state_json = EXCLUDED.state_json,
                updated_at = now()
    """, (session_key, json.dumps(state)))


def delete_session(session_key: str):
    _ensure_table_once()
    execute("DELETE FROM interview_sessions WHERE session_key = %s", (session_key,))


def purge_old_sessions(hours: int = 24):
    _ensure_table_once()
    """Remove sessions older than `hours` hours (call periodically)."""
    execute(
        "DELETE FROM interview_sessions WHERE updated_at < now() - (%s || ' hours')::interval",
        (str(hours),)
    )
