from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from typing import Any

from common.redis_client import get_redis_client, redis_enabled
from common.runtime_config import optional_env


def _redis():
    client = get_redis_client()
    if client is None:
        raise RuntimeError("Redis unavailable")
    return client


def rate_limit_check(key: str, max_calls: int, window_seconds: int) -> bool:
    """Return True if allowed."""
    if not redis_enabled():
        return True
    now = time.time()
    redis = _redis()
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, now - window_seconds)
    pipe.zcard(key)
    pipe.zadd(key, {f"{now}:{uuid.uuid4().hex}": now})
    pipe.expire(key, window_seconds + 1)
    _, count, _, _ = pipe.execute()
    return int(count) < max_calls


def cache_get_json(key: str) -> Any | None:
    if not redis_enabled():
        return None
    raw = _redis().get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    if not redis_enabled():
        return
    payload = json.dumps(value) if not isinstance(value, str) else value
    _redis().setex(key, ttl_seconds, payload)


def _max_interview_slots() -> int:
    try:
        slots = int(optional_env("INTERVIEW_MAX_CONCURRENT", "12"))
    except (TypeError, ValueError):
        slots = 12
    return max(1, min(slots, 64))


def _queue_wait_seconds() -> int:
    try:
        return max(5, min(int(optional_env("INTERVIEW_QUEUE_WAIT_SECONDS", "90")), 300))
    except (TypeError, ValueError):
        return 90


@contextmanager
def redis_interview_turn_slot():
    if not redis_enabled():
        yield {"queue_position": 0}
        return

    redis = _redis()
    max_slots = _max_interview_slots()
    wait_s = _queue_wait_seconds()
    token = uuid.uuid4().hex
    active_key = "ic:interview:active"
    wait_key = "ic:interview:waiting"

    position = int(redis.incr(wait_key))
    redis.expire(wait_key, wait_s + 60)
    deadline = time.time() + wait_s
    acquired = False
    try:
        while time.time() < deadline:
            current = int(redis.get(active_key) or 0)
            if current < max_slots:
                pipe = redis.pipeline()
                pipe.incr(active_key)
                pipe.expire(active_key, 600)
                new_count, _ = pipe.execute()
                if int(new_count) <= max_slots:
                    acquired = True
                    break
                redis.decr(active_key)
            time.sleep(0.25)
        if not acquired:
            from common.interview_capacity import InterviewCapacityError

            raise InterviewCapacityError(
                f"Interview AI is busy ({position} request(s) ahead). Please wait and try again.",
                retry_after=20,
            )
        yield {"queue_position": max(0, position - 1)}
    finally:
        redis.decr(wait_key)
        if acquired:
            redis.decr(active_key)
