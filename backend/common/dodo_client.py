"""Dodo Payments API client for checkout session creation."""

from __future__ import annotations

import logging

import requests as http_requests

from common.runtime_config import optional_env, require_env

logger = logging.getLogger(__name__)

_DODO_API_BASES = {
    "test": "https://test.dodopayments.com",
    "live": "https://api.dodopayments.com",
}

DEFAULT_CHECKOUT_EXPIRY_MINUTES = 30
DEFAULT_AMOUNT_PAISE = 49900


def dodo_api_base() -> str:
    env = optional_env("DODO_ENV", "test").lower()
    override = optional_env("DODO_API_BASE_URL", "")
    if override:
        return override.rstrip("/")
    return _DODO_API_BASES.get(env, _DODO_API_BASES["test"])


def checkout_amount_paise() -> int:
    raw = optional_env("DODO_CHECKOUT_AMOUNT_PAISE", str(DEFAULT_AMOUNT_PAISE))
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_AMOUNT_PAISE


def checkout_expiry_minutes() -> int:
    raw = optional_env("DODO_CHECKOUT_EXPIRY_MINUTES", str(DEFAULT_CHECKOUT_EXPIRY_MINUTES))
    try:
        return max(5, int(raw))
    except ValueError:
        return DEFAULT_CHECKOUT_EXPIRY_MINUTES


def _api_key() -> str:
    return require_env("DODO_PAYMENTS_API_KEY")


def product_id() -> str:
    return require_env("DODO_PRODUCT_ID")


class DodoClientError(Exception):
    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def create_checkout_session(
    *,
    checkout_intent_id: str,
    user_id: str,
    user_email: str,
    user_name: str,
    resume_id: str,
    jd_id: str,
    question_set: int,
    retake_from: str | None,
    return_url: str,
) -> dict:
    """Create a Dodo checkout session and return {checkout_url, session_id}."""
    metadata = {
        "checkout_intent_id": checkout_intent_id,
        "user_id": user_id,
        "resume_id": resume_id,
        "jd_id": jd_id,
        "question_set": str(question_set),
    }
    if retake_from:
        metadata["retake_from"] = retake_from

    payload = {
        "product_cart": [{"product_id": product_id(), "quantity": 1}],
        "customer": {
            "email": user_email,
            "name": user_name or user_email,
        },
        "return_url": return_url,
        "metadata": metadata,
    }

    url = f"{dodo_api_base()}/checkouts"
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }

    try:
        response = http_requests.post(url, json=payload, headers=headers, timeout=30)
    except http_requests.RequestException as exc:
        logger.exception("Dodo checkout session request failed")
        raise DodoClientError(f"Dodo API request failed: {exc}") from exc

    if not response.ok:
        logger.error("Dodo checkout error %s: %s", response.status_code, response.text[:500])
        raise DodoClientError(
            "Dodo checkout session creation failed",
            status_code=response.status_code,
            response_body=response.text,
        )

    data = response.json()
    checkout_url = data.get("checkout_url") or data.get("url")
    session_id = (
        data.get("session_id")
        or data.get("checkout_session_id")
        or data.get("id")
    )
    if not checkout_url:
        raise DodoClientError("Dodo response missing checkout_url", response_body=str(data))

    return {"checkout_url": checkout_url, "session_id": session_id}
