from __future__ import annotations

from common.runtime_config import optional_env

_client = None
_backend = None


def _redis_url() -> str:
    return optional_env("REDIS_URL", "").strip()


def redis_enabled() -> bool:
    return bool(_redis_url())


def get_redis_client():
    global _client
    if _client is not None:
        return _client
    url = _redis_url()
    if not url:
        return None
    import redis

    _client = redis.from_url(url, decode_responses=True)
    return _client


def cache_get(key: str) -> str | None:
    client = get_redis_client()
    if client is None:
        return None
    try:
        return client.get(key)
    except Exception:
        return None


def cache_set(key: str, value: str, ttl_seconds: int) -> None:
    client = get_redis_client()
    if client is None:
        return
    try:
        client.setex(key, ttl_seconds, value)
    except Exception:
        pass
