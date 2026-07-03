"""Session cookie and resolve_request_user tests."""
import time

import jwt
import pytest
from flask import Flask

import common.runtime_config as runtime_config
from tests.test_constants import TEST_JWT_SECRET

runtime_config._LOADED = True
runtime_config._CONFIG = {
    "JWT_SECRET": TEST_JWT_SECRET,
    "DOMAIN": "http://localhost:5173",
    "AUTH_RETURN_TOKEN_IN_BODY": "false",
}

from common.auth import create_token, resolve_request_user
from common.auth_cookies import (
    AUTH_COOKIE_NAME,
    clear_auth_cookie,
    include_token_in_auth_body,
    set_auth_cookie,
)


@pytest.fixture
def app():
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    return flask_app


def test_include_token_in_auth_body_false_in_prod_mode():
    runtime_config._CONFIG["AUTH_RETURN_TOKEN_IN_BODY"] = "false"
    runtime_config._CONFIG["DOMAIN"] = "https://www.ugaanlabs.ai"
    assert include_token_in_auth_body() is False


def test_include_token_in_auth_body_respects_explicit_flag():
    runtime_config._CONFIG["AUTH_RETURN_TOKEN_IN_BODY"] = "true"
    assert include_token_in_auth_body() is True
    runtime_config._CONFIG["AUTH_RETURN_TOKEN_IN_BODY"] = "false"
    assert include_token_in_auth_body() is False


def test_set_and_clear_auth_cookie(app):
    token = create_token("1", "user@example.com")
    with app.test_request_context("/"):
        resp = app.response_class()
        set_auth_cookie(resp, token)
        cookies = resp.headers.getlist("Set-Cookie")
        assert any(AUTH_COOKIE_NAME in c and "HttpOnly" in c for c in cookies)

        clear_auth_cookie(resp)
        cleared = resp.headers.getlist("Set-Cookie")
        assert any(AUTH_COOKIE_NAME in c and "Max-Age=0" in c for c in cleared)


def test_resolve_request_user_from_cookie(app):
    token = create_token("7", "cookie@example.com", full_name="Cookie User")
    with app.test_request_context("/", headers={"Cookie": f"{AUTH_COOKIE_NAME}={token}"}):
        user = resolve_request_user()
        assert user is not None
        assert user["id"] == "7"
        assert user["email"] == "cookie@example.com"


def test_resolve_request_user_from_bearer_header(app):
    token = create_token("8", "bearer@example.com")
    with app.test_request_context("/", headers={"Authorization": f"Bearer {token}"}):
        user = resolve_request_user()
        assert user is not None
        assert user["id"] == "8"


def test_resolve_request_user_cookie_preferred_over_bearer(app):
    cookie_token = create_token("9", "cookie-wins@example.com")
    bearer_token = create_token("10", "bearer-loses@example.com")
    with app.test_request_context(
        "/",
        headers={
            "Cookie": f"{AUTH_COOKIE_NAME}={cookie_token}",
            "Authorization": f"Bearer {bearer_token}",
        },
    ):
        user = resolve_request_user()
        assert user["email"] == "cookie-wins@example.com"


def test_resolve_request_user_allow_expired(app):
    expired_payload = {
        "user_id": "11",
        "email": "expired@example.com",
        "full_name": "",
        "plan": "basic",
        "exp": int(time.time()) - 120,
    }
    token = jwt.encode(expired_payload, TEST_JWT_SECRET, algorithm="HS256")
    with app.test_request_context("/", headers={"Cookie": f"{AUTH_COOKIE_NAME}={token}"}):
        assert resolve_request_user(allow_expired=False) is None
        user = resolve_request_user(allow_expired=True)
        assert user["id"] == "11"
