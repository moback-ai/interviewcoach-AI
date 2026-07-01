import os
import jwt
import bcrypt
from functools import wraps
from flask import request, jsonify
from datetime import datetime, timedelta

from common.runtime_config import load_runtime_config, require_env
from common.auth_cookies import AUTH_COOKIE_NAME

load_runtime_config()


def _get_jwt_secret():
    return require_env("JWT_SECRET")


def _ensure_jwt_secret():
    jwt_secret = _get_jwt_secret()
    if not jwt_secret or jwt_secret == "change-this-secret":
        raise RuntimeError("JWT_SECRET is not configured. Generate one with `openssl rand -hex 32`.")
    return jwt_secret

# ── Token creation ─────────────────────────────────────────────────────────────

def create_token(user_id: str, email: str, full_name: str = "", plan: str = "basic") -> str:
    jwt_secret = _ensure_jwt_secret()
    payload = {
        "user_id": str(user_id),
        "email": email,
        "full_name": full_name,
        "plan": plan,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


def user_from_payload(payload: dict) -> dict:
    return {
        "id": payload["user_id"],
        "email": payload["email"],
        "full_name": payload.get("full_name", ""),
        "plan": payload.get("plan", "basic"),
        "user_metadata": {"full_name": payload.get("full_name", "")},
    }


def decode_auth_token(token: str, *, allow_expired: bool = False) -> dict:
    """Decode JWT and return request.user-shaped dict. Raises jwt.InvalidTokenError."""
    jwt_secret = _ensure_jwt_secret()
    options = {"verify_exp": not allow_expired}
    payload = jwt.decode(token, jwt_secret, algorithms=["HS256"], options=options)
    return user_from_payload(payload)


def authenticate_bearer_token(auth_header: str, *, allow_expired: bool = False):
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        return decode_auth_token(token, allow_expired=allow_expired)
    except jwt.InvalidTokenError:
        return None


def resolve_request_user(*, allow_expired: bool = False):
    from flask import request

    token = (request.cookies.get(AUTH_COOKIE_NAME) or "").strip()
    if token:
        try:
            return decode_auth_token(token, allow_expired=allow_expired)
        except jwt.InvalidTokenError:
            pass
    return authenticate_bearer_token(
        request.headers.get("Authorization", ""),
        allow_expired=allow_expired,
    )


def authenticate_socket_auth(auth_payload, *, allow_expired: bool = False):
    from flask import request as flask_request

    if isinstance(auth_payload, dict):
        token = (auth_payload.get("token") or "").strip()
        if token:
            try:
                return decode_auth_token(token, allow_expired=allow_expired)
            except jwt.InvalidTokenError:
                pass
    token = (flask_request.cookies.get(AUTH_COOKIE_NAME) or "").strip()
    if token:
        try:
            return decode_auth_token(token, allow_expired=allow_expired)
        except jwt.InvalidTokenError:
            pass
    return None

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ── Decorators ───────────────────────────────────────────────────────────────

def verify_auth_token(f):
    """
    Verifies our own JWT and populates request.user with the shape the app
    expects: request.user.get('id'), request.user.get('email').
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)

        user = resolve_request_user(allow_expired=False)
        if not user:
            return jsonify({"error": "No valid authorization"}), 401
        request.user = user
        return f(*args, **kwargs)

    return decorated


def verify_auth_token_allow_expired(f):
    """Accept a valid JWT even after expiry (refresh flow only)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)

        user = resolve_request_user(allow_expired=True)
        if not user:
            return jsonify({"error": "Invalid or expired token"}), 401
        request.user = user
        return f(*args, **kwargs)

    return decorated


def optional_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
        request.user = resolve_request_user(allow_expired=False)
        if request.user is None and request.headers.get('Authorization', '').startswith('Bearer '):
            token = request.headers.get('Authorization', '').split(' ', 1)[1]
            try:
                request.user = decode_auth_token(token, allow_expired=False)
            except Exception:
                pass
        return f(*args, **kwargs)
    return decorated
