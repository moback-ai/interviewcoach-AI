"""Enforce https://www canonical URLs in production."""
from __future__ import annotations

from urllib.parse import urlparse

from common.runtime_config import config_source, optional_env, require_env


def is_local_dev() -> bool:
    return config_source() == "environment"


def enforce_https_www() -> bool:
    if is_local_dev():
        return False
    flag = optional_env("ENFORCE_HTTPS_WWW", "true").lower()
    return flag not in {"0", "false", "no", "off"}


def canonical_host() -> str:
    frontend = optional_env("FRONTEND_DOMAIN", "").strip().lower()
    if frontend:
        return frontend.removeprefix("https://").removeprefix("http://").strip("/")
    domain = require_env("DOMAIN").rstrip("/")
    parsed = urlparse(domain if "://" in domain else f"https://{domain}")
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        return host
    return f"www.{host}" if host else host


def apex_host() -> str:
    host = canonical_host()
    return host[4:] if host.startswith("www.") else host


def normalize_public_origin() -> str:
    return f"https://{canonical_host()}"


def _is_internal_health_request(host: str, path: str) -> bool:
    if not path.rstrip("/").endswith("/api/health"):
        return False
    return host.endswith(".amazonaws.com") or host.endswith(".elb.amazonaws.com")


def effective_request_proto(headers, scheme: str) -> str:
    for key in ("CloudFront-Forwarded-Proto", "X-Forwarded-Proto"):
        raw = headers.get(key)
        if raw:
            return raw.split(",")[0].strip().lower()
    return (scheme or "http").lower()


def canonical_redirect_url(host: str, proto: str, path: str, query_string: bytes) -> str | None:
    host = (host or "").split(":")[0].lower()
    proto = (proto or "http").split(",")[0].strip().lower()
    canonical = canonical_host()
    apex = apex_host()

    if host in {"localhost", "127.0.0.1"}:
        return None

    if _is_internal_health_request(host, path):
        return None

    if host.endswith(".amazonaws.com") or host.endswith(".elb.amazonaws.com"):
        return None

    if host != apex and host != canonical and not host.endswith(f".{apex}"):
        return None

    target_path = path or "/"
    if query_string:
        qs = query_string.decode("utf-8", errors="replace")
        if qs:
            target_path = f"{target_path}?{qs}"

    if host == canonical and proto == "https":
        return None

    return f"https://{canonical}{target_path}"
