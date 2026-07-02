"""Liveness and readiness probes for deploy and load balancer checks."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from common.llm.factory import get_llm_diagnostics, provider_name as llm_provider_name
from common.redis_client import get_redis_client, redis_enabled
from common.runtime_config import config_source, optional_env
from common.speech.factory import get_stt_diagnostics


def live_payload() -> dict[str, Any]:
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }


def _db_ready() -> tuple[bool, str]:
    try:
        from common.db import query_one

        query_one("SELECT 1 AS ok")
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _redis_ready() -> tuple[bool, str]:
    if not redis_enabled():
        return True, ""
    try:
        client = get_redis_client()
        if client is None:
            return False, "redis client unavailable"
        client.ping()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _llm_ready() -> tuple[bool, dict[str, Any]]:
    diag = get_llm_diagnostics()
    return bool(diag.get("ready", False)), diag


def _stt_ready() -> tuple[bool, dict[str, Any]]:
    diag = get_stt_diagnostics()
    chain = diag.get("chain") or []
    for provider in chain:
        block = diag.get(provider)
        if isinstance(block, dict) and block.get("ready"):
            return True, diag
    return False, diag


def readiness_status() -> tuple[bool, dict[str, Any]]:
    failures: list[str] = []
    checks: dict[str, Any] = {}

    db_ok, db_err = _db_ready()
    checks["database"] = {"ready": db_ok, "error": db_err}
    if not db_ok:
        failures.append("database")

    source = config_source()
    config_ok = source not in {"unset", ""}
    checks["config"] = {"ready": config_ok, "source": source}
    if not config_ok:
        failures.append("config")

    redis_ok, redis_err = _redis_ready()
    checks["redis"] = {"ready": redis_ok, "error": redis_err}
    if not redis_ok:
        failures.append("redis")

    llm_ok, llm_diag = _llm_ready()
    checks["llm"] = llm_diag
    if not llm_ok:
        failures.append("llm")

    stt_ok, stt_diag = _stt_ready()
    checks["stt"] = stt_diag
    if not stt_ok:
        failures.append("stt")

    return len(failures) == 0, {"checks": checks, "failures": failures}


def _llm_status_block() -> dict[str, Any]:
    llm_diagnostics = get_llm_diagnostics()
    provider = llm_provider_name()
    return {
        "provider": provider,
        "ready": llm_diagnostics.get("ready", False),
        "reachable": llm_diagnostics.get("reachable", llm_diagnostics.get("ready", False)),
        "model": llm_diagnostics.get("model"),
        "model_available": llm_diagnostics.get(
            "model_available", llm_diagnostics.get("ready", False)
        ),
        "error": llm_diagnostics.get("error", ""),
    }


def full_health_payload() -> dict[str, Any]:
    ready, readiness = readiness_status()
    llm_status = _llm_status_block()
    stt_diagnostics = get_stt_diagnostics()
    provider = llm_provider_name()
    services: dict[str, Any] = {
        "llm": llm_status,
        "stt": stt_diagnostics,
    }
    if provider == "ollama":
        services["ollama"] = dict(llm_status)
    return {
        "status": "healthy" if ready else "degraded",
        "ready": ready,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "api_revision": "prod-v1",
        "config": {
            "source": config_source(),
            "secret_id": optional_env("AWS_SECRETS_MANAGER_SECRET_ID")
            or os.getenv("AWS_SECRETS_MANAGER_SECRET_ID", ""),
        },
        "readiness": readiness,
        "services": services,
    }


def ready_payload() -> dict[str, Any]:
    ready, readiness = readiness_status()
    payload = {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "timestamp": datetime.utcnow().isoformat(),
        "readiness": readiness,
    }
    return payload
