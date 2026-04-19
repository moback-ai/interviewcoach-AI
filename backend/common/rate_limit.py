"""
rate_limit.py
Simple in-process rate limiter using a sliding window counter.
For multi-worker deployments, swap the _store dict for a Redis backend.
"""
import time
import threading
from flask import request, jsonify
from functools import wraps

_lock = threading.Lock()
_store: dict[str, list[float]] = {}  # key -> list of hit timestamps


def _client_key(prefix: str) -> str:
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    return f"{prefix}:{ip}"


def _user_key(prefix: str) -> str:
    user = getattr(request, "user", None)
    uid = user.get("id", "anon") if user else "anon"
    return f"{prefix}:user:{uid}"


def _check(key: str, max_calls: int, window_seconds: int) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
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
    """
    Decorator. Default key is IP-based.
    Usage:
        @rate_limit(max_calls=5, window_seconds=60)
        def login(): ...
    """
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
    """Rate limit by authenticated user ID (falls back to IP for anon)."""
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
