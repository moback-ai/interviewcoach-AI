"""HttpOnly session cookie helpers (preferred over localStorage JWT in production)."""
from __future__ import annotations

from common.canonical_url import is_local_dev
from common.runtime_config import optional_env

AUTH_COOKIE_NAME = optional_env("AUTH_COOKIE_NAME", "ic_session")
AUTH_COOKIE_MAX_AGE = int(optional_env("AUTH_COOKIE_MAX_AGE_SECONDS", str(7 * 24 * 3600)))


def auth_cookie_secure() -> bool:
    override = optional_env("AUTH_COOKIE_SECURE", "").lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    return not is_local_dev()


def set_auth_cookie(response, token: str):
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        httponly=True,
        secure=auth_cookie_secure(),
        samesite="Lax",
        max_age=AUTH_COOKIE_MAX_AGE,
        path="/",
    )
    return response


def clear_auth_cookie(response):
    response.set_cookie(
        AUTH_COOKIE_NAME,
        "",
        httponly=True,
        secure=auth_cookie_secure(),
        samesite="Lax",
        max_age=0,
        path="/",
    )
    return response


def include_token_in_auth_body() -> bool:
    """Return JWT in JSON for local dev; production uses HttpOnly cookie only."""
    flag = optional_env("AUTH_RETURN_TOKEN_IN_BODY", "").lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    if flag in {"0", "false", "no", "off"}:
        return False
    return is_local_dev()
