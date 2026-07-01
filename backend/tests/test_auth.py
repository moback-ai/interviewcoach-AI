import time

import jwt
import pytest

import common.runtime_config as runtime_config
from tests.test_constants import TEST_JWT_SECRET

runtime_config._LOADED = True
runtime_config._CONFIG = {
    "JWT_SECRET": TEST_JWT_SECRET,
    "DOMAIN": "http://localhost:5173",
}

from common.auth import (
    check_password,
    create_token,
    decode_auth_token,
    hash_password,
)
from common.service_hours import service_hours_status


def test_hash_and_check_password_roundtrip():
    raw = "InterviewCoach!test9"
    hashed = hash_password(raw)
    assert hashed != raw
    assert check_password(raw, hashed)
    assert not check_password("wrong-password", hashed)


def test_create_token_encodes_expected_claims():
    token = create_token("user-42", "dev@example.com", full_name="Dev User", plan="pro")
    payload = jwt.decode(
        token,
        TEST_JWT_SECRET,
        algorithms=["HS256"],
    )
    assert payload["user_id"] == "user-42"
    assert payload["email"] == "dev@example.com"
    assert payload["full_name"] == "Dev User"
    assert payload["plan"] == "pro"
    assert "exp" in payload


def test_create_token_rejects_default_secret():
    runtime_config._CONFIG["JWT_SECRET"] = "change-this-secret"
    try:
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            create_token("1", "a@b.com")
    finally:
        runtime_config._CONFIG["JWT_SECRET"] = TEST_JWT_SECRET


def test_decode_auth_token_allows_expired_when_requested():
    expired_payload = {
        "user_id": "9",
        "email": "expired@example.com",
        "full_name": "Expired",
        "plan": "basic",
        "exp": int(time.time()) - 60,
    }
    token = jwt.encode(expired_payload, TEST_JWT_SECRET, algorithm="HS256")

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_auth_token(token, allow_expired=False)

    user = decode_auth_token(token, allow_expired=True)
    assert user["id"] == "9"
    assert user["email"] == "expired@example.com"


def test_service_hours_status_shape():
    status = service_hours_status()
    assert "is_open" in status
    assert "timezone" in status
    assert "start" in status
    assert "end" in status
    assert status["end"] == "19:00"


def test_service_hours_closed_message():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    closed_at = datetime(2026, 7, 1, 22, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    status = service_hours_status(now=closed_at)
    assert status["is_open"] is False
    assert status["title"] == "Under maintenance"
    assert "under maintenance" in status["message"].lower()
    assert "10:00 AM" in status["message"]
    assert "7:00 PM" in status["message"]
