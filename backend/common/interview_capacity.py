"""Limit concurrent Ollama-heavy interview turns on the API host."""
from __future__ import annotations

import threading
from contextlib import contextmanager

from common.runtime_config import optional_env


class InterviewCapacityError(Exception):
    """Raised when all interview slots are busy."""

    def __init__(self, message=None, retry_after=15):
        super().__init__(message or "Interview AI is busy. Please try again shortly.")
        self.retry_after = retry_after


_lock = threading.Lock()
_semaphore = None


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


@contextmanager
def interview_turn_slot():
    sem = _get_semaphore()
    if not sem.acquire(blocking=False):
        raise InterviewCapacityError()
    try:
        yield
    finally:
        sem.release()
