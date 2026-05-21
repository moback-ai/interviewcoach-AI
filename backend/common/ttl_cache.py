"""Tiny in-process TTL cache for expensive read-mostly calls."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def cached(key: str, ttl_seconds: float, producer: Callable[[], T]) -> T:
    now = time.monotonic()
    with _lock:
        entry = _store.get(key)
        if entry and entry[0] > now:
            return entry[1]
    value = producer()
    with _lock:
        _store[key] = (now + ttl_seconds, value)
    return value


def invalidate(key: str) -> None:
    with _lock:
        _store.pop(key, None)
