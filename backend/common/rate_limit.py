"""Rate limiting with Redis when REDIS_URL is set, else in-process fallback."""
import time
import threading
from flask import request, jsonify
from functools import wraps

from common.redis_client import redis_enabled
from common.redis_store import rate_limit_check as redis_rate_limit_check

_lock = threading.Lock()
_store: dict[str, list[float]] = {}


def _client_key(prefix: str) -> str:
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    return f"{prefix}:{ip}"


def _user_key(prefix: str) -> str:
    user = getattr(request, "user", None)
    uid = user.get("id", "anon") if user else "anon"
    return f"{prefix}:user:{uid}"


def _check(key: str, max_calls: int, window_seconds: int) -> bool:
    if redis_enabled():
        return redis_rate_limit_check(f"ic:rl:{key}", max_calls, window_seconds)

    now = time.time()
    cutoff = now - window_seconds
    with _lock:
        hits = _store.get(key, [])
        hits = [t for t in hits if t > cutoff]
        if len(hits) >= max_calls:
            _store[key] = hits
            return False
        hits.append(now)
        _store[key] = hits
    return True


def rate_limit(max_calls: int, window_seconds: int, key_fn=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if request.method == "OPTIONS":
                return f(*args, **kwargs)
            key = key_fn(f.__name__) if key_fn else _client_key(f.__name__)
            if not _check(key, max_calls, window_seconds):
                return jsonify({"error": "Too many requests. Please try again later."}), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator


def user_rate_limit(max_calls: int, window_seconds: int):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if request.method == "OPTIONS":
                return f(*args, **kwargs)
            key = _user_key(f.__name__)
            if not _check(key, max_calls, window_seconds):
                return jsonify({"error": "Too many requests. Please try again later."}), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator
