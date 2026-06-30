"""Dodo webhook signature verification and event parsing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import time
from typing import Any

from common.runtime_config import optional_env, require_env

logger = logging.getLogger(__name__)

TIMESTAMP_TOLERANCE_SECONDS = 300


class WebhookVerificationError(Exception):
    pass


def _constant_time_compare(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _extract_v1_signature(sig_raw: str) -> str:
    if not sig_raw:
        return ""
    match_eq = re.search(r"(?:^|,\s*)v1=([A-Za-z0-9+/=]+)(?:,|$)", sig_raw)
    if match_eq:
        return match_eq.group(1)
    match_comma = re.search(r"(?:^|,\s*)v1,([A-Za-z0-9+/=]+)(?:,|$)", sig_raw)
    if match_comma:
        return match_comma.group(1)
    if "," in sig_raw:
        return sig_raw.split(",", 1)[1].strip()
    return sig_raw.strip()


def _webhook_secret() -> str:
    return require_env("DODO_WEBHOOK_SECRET")


def _test_mode_allowed(headers: dict) -> bool:
    if optional_env("DODO_WEBHOOK_TEST_MODE", "").lower() not in ("1", "true", "yes"):
        return False
    return headers.get("X-Test-Mode", "").lower() == "true"


def verify_webhook_signature(headers: dict, raw_body: bytes) -> None:
    """Verify Dodo/Svix-style webhook signature. Raises WebhookVerificationError on failure."""
    if _test_mode_allowed(headers):
        logger.warning("Dodo webhook signature verification skipped (test mode)")
        return

    webhook_id = headers.get("Webhook-Id") or headers.get("webhook-id") or headers.get("svix-id") or ""
    timestamp = headers.get("Webhook-Timestamp") or headers.get("webhook-timestamp") or headers.get("svix-timestamp") or ""
    sig_raw = headers.get("Webhook-Signature") or headers.get("webhook-signature") or headers.get("svix-signature") or ""

    if not webhook_id or not timestamp or not sig_raw:
        raise WebhookVerificationError("Missing required webhook headers")

    try:
        ts_int = int(timestamp)
    except ValueError as exc:
        raise WebhookVerificationError("Invalid webhook timestamp") from exc

    now = int(time.time())
    if abs(now - ts_int) > TIMESTAMP_TOLERANCE_SECONDS:
        raise WebhookVerificationError("Webhook timestamp outside tolerance window")

    secret_raw = _webhook_secret()
    cleaned = secret_raw.removeprefix("whsec_")
    try:
        key_bytes = base64.b64decode(cleaned)
    except Exception as exc:
        raise WebhookVerificationError("Invalid webhook secret encoding") from exc

    signed_content = f"{webhook_id}.{timestamp}.{raw_body.decode('utf-8')}"
    computed = base64.b64encode(
        hmac.new(key_bytes, signed_content.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")
    received = _extract_v1_signature(sig_raw)

    if not received or not _constant_time_compare(computed, received):
        raise WebhookVerificationError("Invalid webhook signature")


def parse_webhook_event(raw_body: bytes) -> dict[str, Any]:
    try:
        return json.loads(raw_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise WebhookVerificationError("Invalid webhook JSON payload") from exc


def extract_payment_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Normalize payment fields from a Dodo webhook event."""
    event_type = event.get("type") or ""
    data = event.get("data") or {}
    if isinstance(data, dict) and "object" in data and isinstance(data["object"], dict):
        payment = data["object"]
    else:
        payment = data if isinstance(data, dict) else {}

    metadata = payment.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    amount = payment.get("total_amount")
    if amount is None:
        amount = payment.get("amount")

    return {
        "event_id": event.get("id") or "",
        "event_type": event_type,
        "payment_id": payment.get("payment_id") or payment.get("id") or "",
        "status": payment.get("status") or "",
        "amount_paise": int(amount) if amount is not None else None,
        "metadata": metadata,
        "raw_payment": payment,
    }
