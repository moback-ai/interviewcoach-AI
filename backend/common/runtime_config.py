import json
import os

import boto3


SECRET_ID_ENV = "AWS_SECRETS_MANAGER_SECRET_ID"
REGION_ENV_CANDIDATES = ("AWS_REGION", "AWS_DEFAULT_REGION")
_LOADED = False
_CONFIG = {}


def _aws_region() -> str:
    for key in REGION_ENV_CANDIDATES:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return "ap-south-1"


def load_runtime_config() -> None:
    global _LOADED, _CONFIG
    if _LOADED:
        return

    secret_id = os.getenv(SECRET_ID_ENV, "").strip()
    if not secret_id:
        raise RuntimeError(
            f"{SECRET_ID_ENV} must be configured. Runtime configuration is loaded only from AWS Secrets Manager."
        )

    client = boto3.client("secretsmanager", region_name=_aws_region())
    response = client.get_secret_value(SecretId=secret_id)
    secret_string = response.get("SecretString", "").strip()
    if not secret_string:
        raise RuntimeError(f"Secret {secret_id} does not contain a SecretString payload.")

    payload = json.loads(secret_string)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Secret {secret_id} must be a JSON object.")

    normalized = {}
    for key, value in payload.items():
        if value is None:
            continue
        normalized[key] = str(value)

    _CONFIG = normalized

    _LOADED = True


def require_env(name: str) -> str:
    load_runtime_config()
    value = _CONFIG.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be provided via AWS Secrets Manager.")
    return value


def optional_env(name: str, default: str = "") -> str:
    load_runtime_config()
    return _CONFIG.get(name, default).strip()
