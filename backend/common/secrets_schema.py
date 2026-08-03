"""Required and optional keys for interviewcoach/prod/app Secrets Manager JSON."""
from __future__ import annotations

from common.runtime_config import all_config_keys, is_secrets_mode, load_runtime_config, optional_env

REQUIRED_SECRET_KEYS = (
    "LLM_PROVIDER",
    "BEDROCK_REGION",
    "BEDROCK_CHAT_MODEL",
    "STT_PRIMARY",
    "S3_BUCKET",
    "STORAGE_BACKEND",
    "STORAGE_PATH",
    "UPLOAD_FOLDER",
    "REDIS_URL",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "JWT_SECRET",
    "DOMAIN",
    "DODO_PAYMENTS_API_KEY",
    "DODO_WEBHOOK_SECRET",
    "DODO_PRODUCT_ID",
    "DODO_ENV",
)

OPTIONAL_SECRET_KEYS = (
    "STT_FALLBACK",
    "BEDROCK_REPORT_MODEL",
    "LLM_MAX_TOKENS",
    "LLM_TEMPERATURE",
    "OPENROUTER_STT_MODEL",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_API_KEY",
    "WHISPER_MODEL",
    "WHISPER_LANGUAGE",
    "STT_S3_BUCKET",
    "TRANSCRIBE_REGION",
    "TRANSCRIBE_LANGUAGE_CODE",
    "INTERVIEW_SERVER_TTS",
    "INTERVIEW_MAX_CONCURRENT",
    "INTERVIEW_QUEUE_WAIT_SECONDS",
    "INTERVIEW_RESPONSE_TIMEOUT_SECONDS",
    "PUBLIC_STORAGE_URL",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_USE_SSL",
    "MAIL_FROM",
    "DB_POOL_MIN",
    "DB_POOL_MAX",
    "FREE_INTERVIEW_LIMIT",
    "DODO_CHECKOUT_EXPIRY_MINUTES",
    "CHECKOUT_MAINTENANCE_TOKEN",
    "ADMIN_LOG_ROOT",
    "BACKEND_API_BASE",
)


def _stt_chain() -> list[str]:
    primary = (optional_env("STT_PRIMARY", "amazon") or "amazon").strip().lower()
    fallback = (optional_env("STT_FALLBACK", "") or "").strip().lower()
    order: list[str] = []
    for name in (primary, fallback):
        for part in name.split(","):
            part = part.strip()
            if part and part not in order:
                order.append(part)
    return order


def validate_secrets_config() -> dict:
    """Return validation report; raise if required keys missing in secrets mode."""
    load_runtime_config()
    if not is_secrets_mode():
        return {"ok": True, "mode": "environment", "missing": []}

    present = all_config_keys()
    required = list(REQUIRED_SECRET_KEYS)
    if "openrouter" in _stt_chain() and "OPENROUTER_API_KEY" not in required:
        required.append("OPENROUTER_API_KEY")
    missing = [key for key in required if key not in present or not optional_env(key)]
    report = {
        "ok": not missing,
        "mode": "secrets_manager",
        "missing": missing,
        "present_count": len(present),
    }
    if missing:
        raise RuntimeError(
            "Secrets Manager JSON is missing required keys: " + ", ".join(missing)
        )
    return report
