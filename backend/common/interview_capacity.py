"""Limit concurrent Ollama-heavy interview turns on the API host."""
from __future__ import annotations

import threading
from contextlib import contextmanager

from common.runtime_config import optional_env
from common.redis_client import redis_enabled
from common.redis_store import redis_interview_turn_slot


class InterviewCapacityError(Exception):
    """Raised when all interview slots are busy."""

    def __init__(self, message=None, retry_after=15):
        super().__init__(message or "Interview AI is busy. Please try again shortly.")
        self.retry_after = retry_after


_lock = threading.Lock()
_semaphore = None
_waiting = 0


def _get_semaphore():
    global _semaphore
    if _semaphore is not None:
        return _semaphore
    with _lock:
        if _semaphore is None:
            try:
                slots = int(optional_env("INTERVIEW_MAX_CONCURRENT", "12"))
            except (TypeError, ValueError):
                slots = 12
            slots = max(1, min(slots, 64))
            _semaphore = threading.BoundedSemaphore(slots)
        return _semaphore


def _queue_wait_seconds() -> int:
    try:
        return max(5, min(int(optional_env("INTERVIEW_QUEUE_WAIT_SECONDS", "90")), 300))
    except (TypeError, ValueError):
        return 90


@contextmanager
def interview_turn_slot():
    if redis_enabled():
        with redis_interview_turn_slot() as slot:
            yield slot
        return

    global _waiting
    sem = _get_semaphore()
    wait_s = _queue_wait_seconds()
    with _lock:
        position = _waiting
        _waiting += 1
    acquired = False
    try:
        acquired = sem.acquire(blocking=True, timeout=wait_s)
        if not acquired:
            msg = (
                f"Interview AI is busy ({position} request(s) ahead). "
                "Please wait and try again."
            )
            raise InterviewCapacityError(msg, retry_after=20)
        yield {"queue_position": position}
    finally:
        with _lock:
            _waiting = max(0, _waiting - 1)
        if acquired:
            sem.release()
