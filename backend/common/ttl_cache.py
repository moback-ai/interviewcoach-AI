"""TTL cache with Redis when REDIS_URL is set, else in-process fallback."""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable, TypeVar

from common.redis_client import redis_enabled
from common.redis_store import cache_get_json, cache_set_json

T = TypeVar("T")

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def cached(key: str, ttl_seconds: float, producer: Callable[[], T]) -> T:
    if redis_enabled():
        hit = cache_get_json(f"ic:cache:{key}")
        if hit is not None:
            return hit
        value = producer()
        try:
            cache_set_json(f"ic:cache:{key}", value, max(1, int(ttl_seconds)))
        except TypeError:
            cache_set_json(f"ic:cache:{key}", json.dumps(value), max(1, int(ttl_seconds)))
        return value

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
    if redis_enabled():
        from common.redis_client import get_redis_client

        client = get_redis_client()
        if client:
            client.delete(f"ic:cache:{key}")
    with _lock:
        _store.pop(key, None)
