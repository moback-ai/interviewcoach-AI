"""Integration-style tests for auth session and execute sandbox policy."""
import json
from unittest.mock import patch

import pytest

import common.runtime_config as runtime_config

runtime_config._LOADED = True
runtime_config._CONFIG = {
    "JWT_SECRET": "test-jwt-secret-for-pytest-only-32chars",
    "DOMAIN": "http://localhost:5173",
    "AUTH_RETURN_TOKEN_IN_BODY": "true",
}


@pytest.fixture
def auth_token():
    from common.auth import create_token

    return create_token("user-test-1", "test@example.com", full_name="Test User")


@pytest.fixture
def client(auth_token):
    with patch("common.secrets_schema.validate_secrets_config"):
        import app as app_module

        app_module.app.config["TESTING"] = True
        return app_module.app.test_client()


def test_login_sets_session_cookie(client):
    with patch("app.get_user_for_auth") as mock_auth, patch("app.check_password", return_value=True):
        mock_auth.return_value = {
            "id": "user-test-1",
            "email": "test@example.com",
            "full_name": "Test User",
            "username": "testuser",
            "plan": "basic",
            "password_hash": "hash",
            "email_verified_at": "2026-01-01T00:00:00Z",
        }
        with patch("app.serialize_user", side_effect=lambda u: u):
            response = client.post(
                "/api/login",
                data=json.dumps({"identifier": "test@example.com", "password": "secret"}),
                content_type="application/json",
            )
    assert response.status_code == 200
    cookies = response.headers.getlist("Set-Cookie")
    assert any("ic_session=" in c and "HttpOnly" in c for c in cookies)
    payload = response.get_json()
    assert payload.get("user") is not None


def test_logout_clears_session_cookie(client):
    response = client.post("/api/logout")
    assert response.status_code == 200
    cookies = response.headers.getlist("Set-Cookie")
    assert any("ic_session=" in c and "Max-Age=0" in c for c in cookies)


def test_me_accepts_session_cookie(client, auth_token):
    client.set_cookie("ic_session", auth_token, domain="localhost")
    with patch("app.query_one") as mock_query, patch("app.serialize_user", side_effect=lambda u: u):
        mock_query.return_value = {
            "id": "user-test-1",
            "email": "test@example.com",
            "full_name": "Test User",
            "plan": "basic",
        }
        response = client.get("/api/me")
    assert response.status_code == 200
    assert response.get_json()["user"]["email"] == "test@example.com"


def test_execute_rejects_javascript(client, auth_token):
    client.set_cookie("ic_session", auth_token, domain="localhost")
    response = client.post(
        "/api/execute",
        data=json.dumps({"code": "console.log(1)", "language": "javascript"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "disabled" in response.get_json().get("message", "").lower()
