from __future__ import annotations

import json
import os

SECRET_ID_ENV = "AWS_SECRETS_MANAGER_SECRET_ID"
REGION_ENV_CANDIDATES = ("AWS_REGION", "AWS_DEFAULT_REGION")
ALLOW_ENV_FLAG = "RUNTIME_CONFIG_ALLOW_ENV"

# Only these may be set in the process environment on prod servers.
# Everything else must live in Secrets Manager JSON.
BOOTSTRAP_ENV_KEYS = frozenset(
    {
        SECRET_ID_ENV,
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        ALLOW_ENV_FLAG,
    }
)

_LOADED = False
_CONFIG: dict[str, str] = {}
_SOURCE = "unset"


def _aws_region() -> str:
    for key in REGION_ENV_CANDIDATES:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return "ap-south-1"


def _allow_env_fallback() -> bool:
    return os.getenv(ALLOW_ENV_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


def config_source() -> str:
    load_runtime_config()
    return _SOURCE


def is_secrets_mode() -> bool:
    load_runtime_config()
    return _SOURCE == "secrets_manager"


def _fetch_secrets(secret_id: str) -> dict[str, str]:
    import boto3

    client = boto3.client("secretsmanager", region_name=_aws_region())
    response = client.get_secret_value(SecretId=secret_id)
    secret_string = response.get("SecretString", "").strip()
    if not secret_string:
        raise RuntimeError(f"Secret {secret_id} does not contain a SecretString payload.")

    payload = json.loads(secret_string)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Secret {secret_id} must be a JSON object.")

    normalized: dict[str, str] = {}
    for key, value in payload.items():
        if value is None:
            continue
        normalized[str(key)] = str(value)
    return normalized


def _load_from_environment() -> dict[str, str]:
    """Laptop-only fallback when RUNTIME_CONFIG_ALLOW_ENV=true."""
    return {
        key: value
        for key, value in os.environ.items()
        if value is not None and str(value).strip()
    }


def load_runtime_config() -> None:
    global _LOADED, _CONFIG, _SOURCE
    if _LOADED:
        return

    secret_id = os.getenv(SECRET_ID_ENV, "").strip()
    if secret_id:
        _CONFIG = _fetch_secrets(secret_id)
        _SOURCE = "secrets_manager"
        _LOADED = True
        return

    if _allow_env_fallback():
        _CONFIG = _load_from_environment()
        _SOURCE = "environment"
        _LOADED = True
        return

    raise RuntimeError(
        f"Production requires {SECRET_ID_ENV}. "
        f"For laptop-only testing set {ALLOW_ENV_FLAG}=true and use backend/.env.prod.example."
    )


def require_env(name: str) -> str:
    load_runtime_config()
    value = _CONFIG.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} must be provided via AWS Secrets Manager secret "
            f"'{os.getenv(SECRET_ID_ENV, 'interviewcoach/prod/app')}'."
        )
    return value


def optional_env(name: str, default: str = "") -> str:
    load_runtime_config()
    return _CONFIG.get(name, default).strip()


def all_config_keys() -> frozenset[str]:
    load_runtime_config()
    return frozenset(_CONFIG.keys())
