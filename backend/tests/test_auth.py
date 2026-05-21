import jwt
import pytest

import common.runtime_config as runtime_config

runtime_config._LOADED = True
runtime_config._CONFIG = {
    "JWT_SECRET": "test-jwt-secret-for-pytest-only-32chars",
    "DOMAIN": "http://localhost:5173",
}

from common.auth import check_password, create_token, hash_password


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
        "test-jwt-secret-for-pytest-only-32chars",
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
        runtime_config._CONFIG["JWT_SECRET"] = "test-jwt-secret-for-pytest-only-32chars"
