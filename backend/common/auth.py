import os
import jwt
import bcrypt
from functools import wraps
from flask import request, jsonify
from datetime import datetime, timedelta

from common.runtime_config import load_runtime_config, require_env

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

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "No valid authorization header"}), 401

        token = auth_header.split(' ', 1)[1]
        try:
            jwt_secret = _ensure_jwt_secret()
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
            request.user = {
                "id": payload["user_id"],
                "email": payload["email"],
                "full_name": payload.get("full_name", ""),
                "plan": payload.get("plan", "basic"),
                "user_metadata": {"full_name": payload.get("full_name", "")}
            }
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        except Exception as e:
            print(f"Token error: {e}")
            return jsonify({"error": "Token verification failed"}), 401

    return decorated


def optional_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
        auth_header = request.headers.get('Authorization', '')
        request.user = None
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
            try:
                jwt_secret = _ensure_jwt_secret()
                payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                request.user = {
                    "id": payload["user_id"],
                    "email": payload["email"],
                    "full_name": payload.get("full_name", ""),
                    "plan": payload.get("plan", "basic"),
                    "user_metadata": {"full_name": payload.get("full_name", "")}
                }
            except Exception:
                pass
        return f(*args, **kwargs)
    return decorated
