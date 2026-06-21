"""
interview_timer.py
Tracks active interview time (paused stopwatch) across leave/resume sessions.
"""
import time

from common.db import execute, query_one
from common.runtime_config import optional_env
from common.session_store import load_session, save_session

TIMER_LAST_TICK_KEY = "_timer_last_tick_at"
DEFAULT_MAX_GAP_SECONDS = 600


def _session_key(interview_id: str, user_id: str) -> str:
    return f"{interview_id}:{user_id}"


def _max_gap_seconds() -> int:
    raw = optional_env("INTERVIEW_TIMER_MAX_GAP_SECONDS", str(DEFAULT_MAX_GAP_SECONDS))
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_MAX_GAP_SECONDS


def _get_started_interview(interview_id: str, user_id: str):
    return query_one(
        "SELECT id, status, active_seconds FROM interviews WHERE id=%s AND user_id=%s",
        (interview_id, user_id),
    )


def _load_timer_state(interview_id: str, user_id: str) -> tuple[int, float | None]:
    row = _get_started_interview(interview_id, user_id)
    if not row:
        return 0, None

    active_seconds = int(row.get("active_seconds") or 0)
    session = load_session(_session_key(interview_id, user_id)) or {}
    last_tick = session.get(TIMER_LAST_TICK_KEY)
    if last_tick is not None:
        try:
            last_tick = float(last_tick)
        except (TypeError, ValueError):
            last_tick = None
    return active_seconds, last_tick


def _save_timer_state(
    interview_id: str,
    user_id: str,
    active_seconds: int,
    last_tick_at: float | None,
    *,
    merge_session: bool = True,
) -> None:
    session_key = _session_key(interview_id, user_id)
    session = load_session(session_key) or {} if merge_session else {}
    if last_tick_at is None:
        session.pop(TIMER_LAST_TICK_KEY, None)
    else:
        session[TIMER_LAST_TICK_KEY] = last_tick_at
    save_session(session_key, session)
    execute(
        "UPDATE interviews SET active_seconds=%s WHERE id=%s AND user_id=%s",
        (active_seconds, interview_id, user_id),
    )


def _apply_tick_delta(
    active_seconds: int,
    last_tick_at: float | None,
    now: float,
) -> tuple[int, float]:
    if last_tick_at is None:
        return active_seconds, now

    gap = now - last_tick_at
    if gap <= 0:
        return active_seconds, now
    if gap <= _max_gap_seconds():
        active_seconds += int(gap)
    return active_seconds, now


def get_active_seconds(interview_id: str, user_id: str, now: float | None = None) -> int:
    """Return active seconds including any open segment (for timeout checks)."""
    row = _get_started_interview(interview_id, user_id)
    if not row:
        return 0

    active_seconds = int(row.get("active_seconds") or 0)
    session = load_session(_session_key(interview_id, user_id)) or {}
    last_tick = session.get(TIMER_LAST_TICK_KEY)
    if last_tick is None:
        return active_seconds

    try:
        last_tick = float(last_tick)
    except (TypeError, ValueError):
        return active_seconds

    now = now if now is not None else time.time()
    gap = now - last_tick
    if 0 < gap <= _max_gap_seconds():
        active_seconds += int(gap)
    return active_seconds


def tick_interview_time(interview_id: str, user_id: str, now: float | None = None) -> int:
    """Advance active time for a STARTED interview; ignores long idle gaps."""
    row = _get_started_interview(interview_id, user_id)
    if not row or row.get("status") != "STARTED":
        return int(row.get("active_seconds") or 0) if row else 0

    now = now if now is not None else time.time()
    active_seconds, last_tick_at = _load_timer_state(interview_id, user_id)
    active_seconds, last_tick_at = _apply_tick_delta(active_seconds, last_tick_at, now)
    _save_timer_state(interview_id, user_id, active_seconds, last_tick_at)
    return active_seconds


def pause_interview_time(interview_id: str, user_id: str, now: float | None = None) -> int:
    """Flush the open segment and pause the timer."""
    row = _get_started_interview(interview_id, user_id)
    if not row or row.get("status") != "STARTED":
        return int(row.get("active_seconds") or 0) if row else 0

    now = now if now is not None else time.time()
    active_seconds, last_tick_at = _load_timer_state(interview_id, user_id)
    active_seconds, _ = _apply_tick_delta(active_seconds, last_tick_at, now)
    _save_timer_state(interview_id, user_id, active_seconds, None)
    return active_seconds


def finalize_interview_time(interview_id: str, user_id: str, now: float | None = None) -> int:
    """Final flush when the interview ends."""
    now = now if now is not None else time.time()
    active_seconds = pause_interview_time(interview_id, user_id, now=now)
    execute(
        "UPDATE interviews SET ended_at=now() WHERE id=%s AND user_id=%s",
        (interview_id, user_id),
    )
    return active_seconds
