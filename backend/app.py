import os
import sys
import json
import time
import traceback
import subprocess
import tempfile
import hashlib
import base64
import io
import secrets
import uuid
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import re
import mimetypes
from urllib.parse import urlencode, urlparse

from flask import Flask, request, jsonify, send_from_directory, abort, render_template_string, Response, stream_with_context, redirect, make_response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from PIL import Image, UnidentifiedImageError
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
import requests as http_requests

# ── Environment ───────────────────────────────────────────────────────────────
from common.runtime_config import load_runtime_config, optional_env, require_env, config_source
from common.lazy_deps import get_cv2, get_numpy, get_soundfile, get_pydub, get_mediapipe, get_inference_device
from common.ttl_cache import cached

load_runtime_config()

from common.secrets_schema import validate_secrets_config

validate_secrets_config()

_ollama_host = (optional_env("OLLAMA_HOST", "") or "").strip()
if _ollama_host:
    os.environ["OLLAMA_HOST"] = _ollama_host.rstrip("/")

INTERVIEW_PATH = os.path.join(os.path.dirname(__file__), "INTERVIEW")
if INTERVIEW_PATH not in sys.path:
    sys.path.append(INTERVIEW_PATH)

SUPPORT_BOT_PATH = os.path.join(os.path.dirname(__file__), "Support-bot")
if SUPPORT_BOT_PATH not in sys.path:
    sys.path.append(SUPPORT_BOT_PATH)

# ── Internal modules ──────────────────────────────────────────────────────────
from common.auth import (
    verify_auth_token,
    verify_auth_token_allow_expired,
    authenticate_socket_auth,
    create_token,
    hash_password,
    check_password,
)
from common.db import query_one, query_all, execute, execute_many
from common.content_hash import (
    hash_resume_bytes,
    hash_skills_list,
    hash_skills_text,
    hash_job_description,
)
from common.email_utils import send_email, smtp_is_configured
from common.storage import (
    save_bytes,
    save_from_path,
    read_bytes,
    list_folder,
    delete_files,
    public_url,
    protected_file_url,
    normalize_file_url,
    resolve_relative_path,
    validated_protected_relative_path,
    build_protected_storage_path,
    user_owns_storage_path,
    safe_storage_file_path,
    send_storage_file,
    validated_legacy_upload_folder,
)
from common.canonical_url import (
    canonical_redirect_url,
    effective_request_proto,
    enforce_https_www,
    is_local_dev,
    normalize_public_origin,
)
from common.auth_cookies import (
    clear_auth_cookie,
    include_token_in_auth_body,
    set_auth_cookie,
)
from common.service_hours import service_hours_status
from common.rate_limit import rate_limit, user_rate_limit
from common.session_store import load_session, save_session, delete_session, purge_old_sessions
from common.interview_timer import (
    TIMER_LAST_TICK_KEY,
    tick_interview_time,
    pause_interview_time,
    finalize_interview_time,
)
from common.interview_capacity import interview_turn_slot, InterviewCapacityError
from common.transcribe_remote import transcribe_via_remote_service
from common.speech.factory import transcribe_audio_file as stt_transcribe_file, get_stt_diagnostics
from common.llm.factory import get_llm_diagnostics, provider_name as llm_provider_name
from common.payment_handlers import (
    checkout_status_handler,
    create_checkout_handler,
    dodo_webhook_handler,
)
from common.interview_handlers import interview_quota_handler, start_interview_handler

try:
    from INTERVIEW.Interview_manager import InterviewManager
    from INTERVIEW.analyze_performance_trends import analyze_user_performance, analyze_performance_from_feedbacks
except Exception as interview_import_error:
    InterviewManager = None

    def _missing_interview_dependency(*args, **kwargs):
        raise RuntimeError(f"Interview AI dependencies are unavailable: {interview_import_error}")

    analyze_user_performance = _missing_interview_dependency
    analyze_performance_from_feedbacks = _missing_interview_dependency
    print(f"[WARN] Interview modules unavailable: {interview_import_error}")

try:
    from Piper.voiceCloner import synthesize_text_to_wav
except Exception as voice_import_error:
    def synthesize_text_to_wav(*args, **kwargs):
        raise RuntimeError(f"Voice cloning dependencies are unavailable: {voice_import_error}")

    print(f"[WARN] Voice cloning unavailable: {voice_import_error}")

_TIMEOUT_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="api-timeout")
_schemas_initialized = False
_server_log_dirs_ready = False

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = int(optional_env("MAX_CONTENT_MB", "200")) * 1024 * 1024

DOMAIN = require_env("DOMAIN")


def _build_cors_origins():
    origins = {normalize_public_origin()}
    if is_local_dev():
        origins.update({
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        })
    return sorted(origins)


_CORS_ORIGINS = _build_cors_origins()
EMAIL_VERIFICATION_TTL_HOURS = int(optional_env("EMAIL_VERIFICATION_TTL_HOURS", "24"))
API_FAILURES_LOG_FILE = os.path.abspath(
    optional_env("API_FAILURES_LOG_FILE", "/apps/logs/server/BACKEND/api-failures.log")
)

CORS(app,
     supports_credentials=True,
     origins=_CORS_ORIGINS,
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept"])

_ALLOWED_ORIGINS = _CORS_ORIGINS
socketio = SocketIO(app, cors_allowed_origins=_ALLOWED_ORIGINS, async_mode="threading")


@app.before_request
def _bootstrap_app_once():
    _ensure_app_schemas_once()


@app.before_request
def _enforce_https_www():
    if not enforce_https_www():
        return None
    target = canonical_redirect_url(
        request.host,
        effective_request_proto(request.headers, request.scheme),
        request.path,
        request.query_string,
    )
    if target:
        return redirect(target, code=301)
    return None


def get_public_origin():
    if enforce_https_www():
        return normalize_public_origin()
    return require_env("DOMAIN").rstrip("/")


def build_public_url(path: str, **params):
    base = f"{get_public_origin()}/{path.lstrip('/')}"
    if not params:
        return base
    return f"{base}?{urlencode(params)}"


def _issue_auth_response(body: dict, token: str | None, status: int = 200):
    payload = dict(body)
    if token and include_token_in_auth_body():
        payload["token"] = token
    resp = make_response(jsonify(payload), status)
    if token:
        set_auth_cookie(resp, token)
    return resp


def hash_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_username(raw_username: str) -> str:
    username = (raw_username or "").strip().lower()
    if not username:
        return ""
    if not all(ch.isalnum() or ch in "._-" for ch in username):
        raise ValueError("Username can only contain letters, numbers, dots, underscores, and hyphens.")
    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters long.")
    return username


def ensure_auth_schema():
    execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT")
    execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname TEXT")
    execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT NOT NULL DEFAULT ''")
    execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS date_of_birth DATE")
    execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS gender TEXT")
    execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ")
    execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_sent_at TIMESTAMPTZ")
    execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique
        ON users ((lower(username)))
        WHERE username IS NOT NULL
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS email_verification_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            consumed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)
    execute("CREATE INDEX IF NOT EXISTS idx_email_verification_lookup ON email_verification_tokens (user_id, expires_at DESC)")


_ALLOWED_DIFFICULTY_EXPERIENCE = frozenset({"beginner", "intermediate", "expert"})
_USER_PUBLIC_FIELDS = (
    "id",
    "username",
    "email",
    "full_name",
    "nickname",
    "avatar_url",
    "date_of_birth",
    "gender",
    "plan",
    "created_at",
    "email_verified_at",
)
_USER_AUTH_FIELDS = (
    "id",
    "email",
    "username",
    "password_hash",
    "full_name",
    "nickname",
    "avatar_url",
    "date_of_birth",
    "gender",
    "plan",
    "created_at",
    "email_verified_at",
)


def normalize_gender(value):
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    if normalized in {"male", "m", "man"}:
        return "male"
    if normalized in {"female", "f", "woman"}:
        return "female"
    if normalized in {"other", "non-binary", "nonbinary", "prefer_not_to_say", "prefer-not-to-say"}:
        return "other"
    raise ValueError("Gender must be male, female, or other")


def build_user_columns(fields, alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return ", ".join(f"{prefix}{field}" for field in fields)


def normalize_question_difficulty(value) -> str:
    if value is None:
        return "medium"
    normalized = str(value).strip().lower()
    if normalized in {"easy", "beginner", "basic", "junior", "novice", "simple"}:
        return "easy"
    if normalized in {"medium", "intermediate", "mid", "moderate", "coding"}:
        return "medium"
    if normalized in {"hard", "expert", "advanced", "senior", "difficult", "complex"}:
        return "hard"
    return "medium"


def normalize_difficulty_experience(value) -> str:
    if value is None:
        return "beginner"
    normalized = str(value).strip().lower()
    if normalized in _ALLOWED_DIFFICULTY_EXPERIENCE:
        return normalized
    if normalized in {"weak", "junior", "novice", "easy", "basic"}:
        return "beginner"
    if normalized in {"medium", "mid", "strong_mid"}:
        return "intermediate"
    if normalized in {"strong", "expert", "senior", "advanced", "hard"}:
        return "expert"
    return "beginner"


def normalize_date_of_birth(value):
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        return datetime.strptime(normalized, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Date of birth must use the YYYY-MM-DD format.") from exc


def serialize_date_value(value):
    if not value:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


QUESTION_ORDER_SQL = """
    CASE
        WHEN lower(coalesce(difficulty_level, '')) IN ('easy', 'beginner', 'basic', 'junior', 'novice', 'simple') THEN 1
        WHEN lower(coalesce(difficulty_level, '')) IN ('medium', 'intermediate', 'mid', 'moderate', 'coding') THEN 2
        WHEN lower(coalesce(difficulty_level, '')) IN ('hard', 'expert', 'advanced', 'senior', 'difficult', 'complex') THEN 3
        ELSE 4
    END,
    lower(coalesce(question_text, '')),
    CASE
        WHEN lower(coalesce(difficulty_experience, '')) IN ('beginner', 'weak', 'easy') THEN 1
        WHEN lower(coalesce(difficulty_experience, '')) IN ('intermediate', 'medium', 'mid') THEN 2
        WHEN lower(coalesce(difficulty_experience, '')) IN ('expert', 'strong', 'hard', 'advanced') THEN 3
        ELSE 4
    END,
    created_at ASC
"""
QUESTION_ORDER_SQL_Q_ALIAS = QUESTION_ORDER_SQL.replace("created_at ASC", "q.created_at ASC")


def format_feedback_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(str(item) for item in value if str(item).strip())
    if value is None:
        return ""
    return json.dumps(value)


def ensure_password_reset_schema():
    execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            consumed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)
    execute("CREATE INDEX IF NOT EXISTS idx_pwd_reset_user ON password_reset_tokens(user_id, expires_at DESC)")


def normalize_feedback_row(row):
    if not row:
        return None
    normalized = dict(row)
    normalized['metrics'] = _normalize_metrics(normalized.get('metrics'))
    normalized['key_strengths'] = _normalize_list(normalized.get('key_strengths'))
    normalized['improvement_areas'] = _normalize_list(normalized.get('improvement_areas'))
    if normalized.get('audio_url'):
        normalized['audio_url'] = normalize_file_url(normalized['audio_url'])
    active = normalized.get('active_seconds') or 0
    normalized['interview_duration_minutes'] = (
        max(1, round(active / 60)) if active > 0 else None
    )
    return normalized


def _serialize_file_url(url_or_path):
    return normalize_file_url(url_or_path)


def _serialize_resume_row(row):
    if not row:
        return row
    data = dict(row)
    if data.get('file_url'):
        data['file_url'] = normalize_file_url(data['file_url'])
    elif data.get('stored_path'):
        data['file_url'] = protected_file_url(data['stored_path'])
    return data


def ensure_questions_schema():
    execute(
        """
        ALTER TABLE questions
        ADD COLUMN IF NOT EXISTS difficulty_experience TEXT NOT NULL DEFAULT 'beginner'
        """
    )


def ensure_dossier_and_content_hash_schema():
    """Idempotent: content_hash columns + interview_dossiers table."""
    execute("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS content_hash TEXT")
    execute("ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS content_hash TEXT")
    execute(
        """
        CREATE INDEX IF NOT EXISTS idx_resumes_user_content_hash
        ON resumes(user_id, content_hash)
        """
    )
    execute(
        """
        CREATE INDEX IF NOT EXISTS idx_jd_user_content_hash
        ON job_descriptions(user_id, content_hash)
        """
    )
    execute(
        """
        CREATE TABLE IF NOT EXISTS interview_dossiers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
            jd_id UUID NOT NULL REFERENCES job_descriptions(id) ON DELETE CASCADE,
            job_title TEXT,
            source TEXT,
            dossier JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (resume_id, jd_id)
        )
        """
    )
    execute(
        """
        CREATE INDEX IF NOT EXISTS idx_interview_dossiers_user_pair
        ON interview_dossiers(user_id, resume_id, jd_id)
        """
    )


def serialize_user(user):
    if not user:
        return None
    payload = dict(user)
    payload["id"] = str(payload["id"])
    payload["email_verified"] = bool(payload.get("email_verified_at"))
    payload["nickname"] = payload.get("nickname") or ""
    payload["avatar_url"] = _serialize_file_url(payload.get("avatar_url") or "") or ""
    payload["date_of_birth"] = serialize_date_value(payload.get("date_of_birth"))
    payload["gender"] = payload.get("gender") or ""
    payload.setdefault("user_metadata", {})
    payload["user_metadata"]["full_name"] = payload.get("full_name", "")
    payload["user_metadata"]["nickname"] = payload["nickname"]
    payload["user_metadata"]["avatar_url"] = payload["avatar_url"]
    payload["user_metadata"]["date_of_birth"] = payload["date_of_birth"]
    payload["user_metadata"]["gender"] = payload["gender"]
    return payload


def _allow_manual_auth_links():
    """Only expose verification/reset links in API responses on local dev."""
    return config_source() == "environment"


def build_verification_payload(user, verification_link, delivery="email"):
    payload = {
        "verification_required": True,
        "message": "Please verify your email before logging in.",
        "email": user["email"],
        "delivery": delivery,
    }
    if delivery != "email":
        payload["verification_link"] = verification_link
    return payload


def issue_email_verification(user, allow_manual_fallback=False):
    execute("UPDATE email_verification_tokens SET consumed_at = now() WHERE user_id = %s AND consumed_at IS NULL", (user["id"],))
    token = secrets.token_urlsafe(32)
    token_hash = hash_verification_token(token)
    verification_link = build_public_url("verify-email", token=token)
    execute(
        """
        INSERT INTO email_verification_tokens (user_id, email, token_hash, expires_at)
        VALUES (%s, %s, %s, now() + (%s || ' hours')::interval)
        """,
        (user["id"], user["email"], token_hash, EMAIL_VERIFICATION_TTL_HOURS),
    )
    execute("UPDATE users SET verification_sent_at = now() WHERE id = %s", (user["id"],))

    text_body = (
        f"Hi {user.get('full_name') or user.get('username') or 'there'},\n\n"
        f"Verify your InterviewCoach account by opening this link:\n{verification_link}\n\n"
        f"This link expires in {EMAIL_VERIFICATION_TTL_HOURS} hours."
    )
    html_body = (
        f"<p>Hi {user.get('full_name') or user.get('username') or 'there'},</p>"
        f"<p>Verify your InterviewCoach account by clicking the link below:</p>"
        f"<p><a href=\"{verification_link}\">{verification_link}</a></p>"
        f"<p>This link expires in {EMAIL_VERIFICATION_TTL_HOURS} hours.</p>"
    )

    if smtp_is_configured():
        send_email("Verify your InterviewCoach account", user["email"], text_body, html_body)
        return build_verification_payload(user, verification_link, delivery="email")

    if allow_manual_fallback and _allow_manual_auth_links():
        print(f"[WARN] SMTP not configured. Verification link for {user['email']}: {verification_link}")
        return build_verification_payload(user, verification_link, delivery="manual")

    raise RuntimeError("SMTP is not configured for verification emails.")


def get_user_for_auth(identifier: str):
    normalized = (identifier or "").strip().lower()
    return query_one(
        """
        SELECT {columns}
        FROM users
        WHERE lower(email) = %s OR lower(coalesce(username, '')) = %s
        """.format(columns=build_user_columns(_USER_AUTH_FIELDS)),
        (normalized, normalized),
    )


def _ensure_app_schemas_once():
    global _schemas_initialized
    if _schemas_initialized:
        return
    ensure_auth_schema()
    ensure_questions_schema()
    ensure_dossier_and_content_hash_schema()
    _schemas_initialized = True


PUBLIC_DOC_ENDPOINTS = {
    "/api/health",
    "/api/health/live",
    "/api/health/ready",
    "/api/service-hours",
    "/api/signup",
    "/api/login",
    "/api/check-email",
    "/api/check-username",
    "/api/resend-verification",
    "/api/verify-email",
    "/api/docs",
    "/api/openapi.json",
    "/storage/{relative_path}",
}

API_DOC_OVERRIDES = {
    "/api/health": {
        "get": {
            "summary": "Health check",
            "description": "Returns backend health for uptime checks and deployment validation.",
        }
    },
    "/api/health/live": {
        "get": {
            "summary": "Liveness probe",
            "description": "Returns 200 when the API process is running.",
        }
    },
    "/api/health/ready": {
        "get": {
            "summary": "Readiness probe",
            "description": "Returns 200 only when database, config, and providers are ready for traffic.",
        }
    },
    "/api/signup": {
        "post": {
            "summary": "Create account",
            "description": "Registers a new user with username, email, full name, and password.",
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["username", "email", "full_name", "password"],
                            "properties": {
                                "username": {"type": "string", "example": "govardhan"},
                                "email": {"type": "string", "format": "email"},
                                "full_name": {"type": "string", "example": "Govardhan Reddy"},
                                "password": {"type": "string", "format": "password"},
                            },
                        }
                    }
                },
            },
        }
    },
    "/api/login": {
        "post": {
            "summary": "Login",
            "description": "Signs in with email or username and returns the auth token and user profile.",
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["identifier", "password"],
                            "properties": {
                                "identifier": {"type": "string", "example": "govardhan"},
                                "password": {"type": "string", "format": "password"},
                            },
                        }
                    }
                },
            },
        }
    },
    "/api/me": {
        "get": {
            "summary": "Current user profile",
            "description": "Returns the currently authenticated user.",
        },
        "put": {
            "summary": "Update current user",
            "description": "Updates the current user's profile fields.",
        },
    },
    "/api/dashboard": {
        "get": {
            "summary": "Dashboard data",
            "description": "Returns resume and job-description pairings, interviews, and summary information for the signed-in user.",
        }
    },
    "/api/upload-resume": {
        "post": {
            "summary": "Upload resume",
            "description": "Uploads a resume file and stores it for later question generation and interviews.",
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {
                                "file": {"type": "string", "format": "binary"},
                            },
                        }
                    }
                },
            },
        }
    },
    "/api/parse-job-description": {
        "post": {
            "summary": "Parse job description",
            "description": "Extracts structured job-description content from uploaded files.",
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {
                                "file": {"type": "string", "format": "binary"},
                            },
                        }
                    }
                },
            },
        }
    },
    "/api/generate-questions": {
        "post": {
            "summary": "Generate interview questions",
            "description": "Generates interview questions for a resume and job-description combination.",
        }
    },
    "/api/transcribe-audio": {
        "post": {
            "summary": "Transcribe audio",
            "description": "Transcribes interview audio uploads.",
        }
    },
    "/api/generate-response": {
        "post": {
            "summary": "Generate AI response",
            "description": "Generates an AI interview/chat response based on the current conversation context.",
        }
    },
    "/api/create-payment": {
        "post": {
            "summary": "Create payment",
            "description": "Creates a payment session or payment link for an interview flow.",
        }
    },
    "/functions/v1/dashboard": {
        "get": {
            "summary": "Dashboard data (frontend alias)",
            "description": "Alias route used by the frontend for dashboard data.",
        }
    },
    "/functions/v1/create-payment": {
        "post": {
            "summary": "Create payment (frontend alias)",
            "description": "Alias route used by the frontend payment flow.",
        }
    },
    "/storage/{relative_path}": {
        "get": {
            "summary": "Download stored file",
            "description": "Serves files from the configured storage path.",
            "parameters": [
                {
                    "name": "relative_path",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
        }
    },
}


def _rule_to_openapi_path(rule: str) -> str:
    return rule.replace("<", "{").replace(">", "}")


def _humanize_endpoint_name(endpoint_name: str) -> str:
    return endpoint_name.replace("_", " ").replace("-", " ").strip().title()


def _default_operation_for_rule(rule, method: str):
    openapi_path = _rule_to_openapi_path(rule.rule)
    operation = {
        "tags": [openapi_path.split("/")[1] if openapi_path.count("/") > 1 else "api"],
        "summary": f"{method.title()} {_humanize_endpoint_name(rule.endpoint)}",
        "responses": {
            "200": {"description": "Successful response"},
            "400": {"description": "Bad request"},
            "401": {"description": "Unauthorized"},
            "500": {"description": "Server error"},
        },
    }
    if method in {"post", "put", "patch"}:
        operation["requestBody"] = {
            "required": False,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": True,
                    }
                }
            },
        }
    if openapi_path not in PUBLIC_DOC_ENDPOINTS:
        operation["security"] = [{"bearerAuth": []}]
    return operation


def build_openapi_spec():
    paths = {}
    for rule in sorted(app.url_map.iter_rules(), key=lambda item: item.rule):
        if rule.endpoint == "static" or rule.rule.startswith("/socket.io"):
            continue
        openapi_path = _rule_to_openapi_path(rule.rule)
        path_item = paths.setdefault(openapi_path, {})
        method_overrides = API_DOC_OVERRIDES.get(openapi_path, {})
        for method in sorted(rule.methods):
            normalized_method = method.lower()
            if normalized_method in {"head", "options"}:
                continue
            operation = _default_operation_for_rule(rule, normalized_method)
            override = method_overrides.get(normalized_method)
            if override:
                operation.update(override)
            path_item[normalized_method] = operation

    current_origin = request.host_url.rstrip("/")
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "InterviewCoach API",
            "version": "2.0.0",
            "description": "OpenAPI documentation for the InterviewCoach backend and frontend alias routes.",
        },
        "servers": [{"url": current_origin}],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            }
        },
        "paths": paths,
    }


@app.route('/api/openapi.json', methods=['GET'])
def openapi_json():
    if not _api_docs_enabled():
        return jsonify({"error": "Not found"}), 404
    return jsonify(build_openapi_spec())


@app.route('/api/docs', methods=['GET'])
def swagger_ui():
    if not _api_docs_enabled():
        return jsonify({"error": "Not found"}), 404
    html = """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>InterviewCoach API Docs</title>
        <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
        <style>
          body { margin: 0; background: #10141c; }
          #swagger-ui { max-width: 1200px; margin: 0 auto; }
        </style>
      </head>
      <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
          window.ui = SwaggerUIBundle({
            url: "/api/openapi.json",
            dom_id: "#swagger-ui",
            deepLinking: true,
            persistAuthorization: true,
            displayRequestDuration: true,
            tryItOutEnabled: true
          });
        </script>
      </body>
    </html>
    """
    return render_template_string(html)




def _api_docs_enabled():
    flag = optional_env("ENABLE_API_DOCS", "").lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    if flag in {"0", "false", "no", "off"}:
        return False
    return config_source() == "environment"


def _extract_request_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip
    return (request.headers.get("X-Real-IP") or request.remote_addr or "").strip()


def _is_admin_user(user):
    if not user:
        return False
    plan = (user.get("plan") or "").strip().lower()
    if plan == "admin":
        return True
    record = query_one("SELECT plan FROM users WHERE id=%s", (user.get("id"),))
    return ((record or {}).get("plan") or "").strip().lower() == "admin"


def _redact_log_text(text: str):
    redacted = text
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9\-_\.]+", "Bearer [REDACTED]", redacted)
    redacted = re.sub(r'("?(?:password|token|secret|authorization|api[_-]?key)"?\s*[:=]\s*)"[^"]+"', r'\1"[REDACTED]"', redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", r"\1***@\2", redacted)
    return redacted


def _ensure_api_failure_log_dir():
    global _server_log_dirs_ready
    if _server_log_dirs_ready:
        return
    os.makedirs(os.path.dirname(API_FAILURES_LOG_FILE), exist_ok=True)
    _server_log_dirs_ready = True


def _append_api_failure_line(status_code: int, detail: str = ""):
    if request.path.startswith((
        "/api/docs",
        "/api/openapi.json",
    )):
        return
    _ensure_api_failure_log_dir()
    timestamp = datetime.utcnow().isoformat() + "Z"
    query_string = request.query_string.decode("utf-8", errors="replace") if request.query_string else ""
    line = (
        f"{timestamp} method={request.method} path={request.path}"
        f" status={status_code} ip={_extract_request_ip()}"
    )
    if query_string:
        line += f" query={query_string[:200]}"
    if detail:
        line += f" detail={detail[:500]}"
    line = _redact_log_text(line) + "\n"
    with open(API_FAILURES_LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(line)


@app.after_request
def _record_api_failure_response(response):
    try:
        if enforce_https_www():
            forwarded = (request.headers.get("X-Forwarded-Proto") or request.scheme or "").lower()
            if forwarded == "https" or request.scheme == "https":
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains; preload",
                )
        if request.path.startswith("/api/") and response.status_code >= 400:
            detail = ""
            if hasattr(response, "get_json"):
                payload = response.get_json(silent=True) or {}
                detail = str(payload.get("error") or payload.get("message") or "")
            _append_api_failure_line(response.status_code, detail=detail)
    except Exception as exc:
        print(f"[WARN] Failed to record API failure log: {exc}")
    return response


@app.errorhandler(Exception)
def _log_unhandled_api_exception(exc):
    if isinstance(exc, HTTPException):
        return exc
    if request.path.startswith("/api/"):
        _append_api_failure_line(500, detail=str(exc))
    raise exc


# ─────────────────────────────────────────────────────────────────────────────
#  HEAD TRACKING
# ─────────────────────────────────────────────────────────────────────────────

class EyeContactDetector_Callib:
    def __init__(self):
        mp = get_mediapipe()
        if not hasattr(mp, "solutions") or not hasattr(mp.solutions, "face_mesh"):
            raise RuntimeError("mediapipe face mesh support is unavailable in this environment")
        self.FACE_3D_IDX = [1, 33, 263, 61, 291, 199]
        self.left_eye_idx = [33, 133, 159, 145]
        self.left_iris_idx = 468
        self.right_eye_idx = [362, 263, 386, 374]
        self.right_iris_idx = 473
        self.calibrated = False
        self.eye_threshold = 0.25
        self.head_threshold = 30
        self.horizontal_eye_limits = (0.2, 0.8)
        self.vertical_eye_limits = (0.2, 0.8)
        self.baseline = {"left_eye": None, "right_eye": None, "yaw": None, "pitch": None}
        self.last_process_time = 0
        self.min_frame_interval = 0.12
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False, max_num_faces=1,
            refine_landmarks=True, min_detection_confidence=0.5, min_tracking_confidence=0.5
        )

    def reset_calibration(self):
        self.calibrated = False
        self.baseline = {"left_eye": None, "right_eye": None, "yaw": None, "pitch": None}

    def get_eye_ratios(self, landmarks, eye_idx, iris_idx, w, h):
        try:
            left = landmarks[eye_idx[0]]; right = landmarks[eye_idx[1]]
            top = landmarks[eye_idx[2]]; bottom = landmarks[eye_idx[3]]
            iris = landmarks[iris_idx]
            x_left, x_right = left.x * w, right.x * w
            y_top, y_bottom = top.y * h, bottom.y * h
            iris_x, iris_y = iris.x * w, iris.y * h
            h_ratio = (iris_x - x_left) / (x_right - x_left + 1e-6)
            v_ratio = (iris_y - y_top) / (y_bottom - y_top + 1e-6)
            return h_ratio, v_ratio
        except Exception:
            return 0.5, 0.5

    def get_head_pose(self, landmarks, w, h):
        try:
            face_2d, face_3d = [], []
            for idx in self.FACE_3D_IDX:
                lm = landmarks[idx]
                x, y = int(lm.x * w), int(lm.y * h)
                face_2d.append([x, y])
                face_3d.append([x, y, lm.z * 3000])
            np = get_numpy()
            cv2 = get_cv2()
            face_2d = np.array(face_2d, dtype=np.float64)
            face_3d = np.array(face_3d, dtype=np.float64)
            cam_matrix = np.array([[w, 0, w / 2], [0, w, h / 2], [0, 0, 1]])
            dist_coeffs = np.zeros((4, 1))
            _, rot_vec, _ = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_coeffs)
            rmat, _ = cv2.Rodrigues(rot_vec)
            angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
            return angles[1], angles[0]
        except Exception:
            return 0.0, 0.0

    def calibrate(self, landmarks, w, h):
        try:
            self.baseline["left_eye"] = self.get_eye_ratios(landmarks, self.left_eye_idx, self.left_iris_idx, w, h)
            self.baseline["right_eye"] = self.get_eye_ratios(landmarks, self.right_eye_idx, self.right_iris_idx, w, h)
            self.baseline["yaw"], self.baseline["pitch"] = self.get_head_pose(landmarks, w, h)
            self.calibrated = True
        except Exception:
            self.calibrated = False

    def _pre_cal_check(self, landmarks, w, h):
        le = self.get_eye_ratios(landmarks, self.left_eye_idx, self.left_iris_idx, w, h)
        re = self.get_eye_ratios(landmarks, self.right_eye_idx, self.right_iris_idx, w, h)
        hl, vl = self.horizontal_eye_limits, self.vertical_eye_limits
        return bool(hl[0] <= le[0] <= hl[1] and hl[0] <= re[0] <= hl[1]
                    and vl[0] <= le[1] <= vl[1] and vl[0] <= re[1] <= vl[1])

    def is_looking_at_camera(self, landmarks, w, h):
        if not self.calibrated:
            return self._pre_cal_check(landmarks, w, h)
        le = self.get_eye_ratios(landmarks, self.left_eye_idx, self.left_iris_idx, w, h)
        re = self.get_eye_ratios(landmarks, self.right_eye_idx, self.right_iris_idx, w, h)
        yaw, pitch = self.get_head_pose(landmarks, w, h)
        np = get_numpy()
        ld = np.sqrt((le[0] - self.baseline["left_eye"][0])**2 + (le[1] - self.baseline["left_eye"][1])**2)
        rd = np.sqrt((re[0] - self.baseline["right_eye"][0])**2 + (re[1] - self.baseline["right_eye"][1])**2)
        return bool(ld < self.eye_threshold and rd < self.eye_threshold
                    and abs(yaw - self.baseline["yaw"]) < self.head_threshold
                    and abs(pitch - self.baseline["pitch"]) < self.head_threshold)

    def process(self, frame, is_calibrating=False):
        now = time.time()
        if now - self.last_process_time < self.min_frame_interval:
            return {"looking": False, "message": "Frame rate limited"}
        self.last_process_time = now
        h, w = frame.shape[:2]
        cv2 = get_cv2()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)
        if not results.multi_face_landmarks:
            return {"looking": False, "ready_for_calibration": False if is_calibrating else None,
                    "message": "No face detected"}
        landmarks = results.multi_face_landmarks[0].landmark
        if is_calibrating:
            if self.calibrated:
                return {"looking": bool(self.is_looking_at_camera(landmarks, w, h))}
            if self._pre_cal_check(landmarks, w, h):
                self.calibrate(landmarks, w, h)
                return {"calibrated": True, "looking": True, "ready_for_calibration": False,
                        "message": "Calibration successful"}
            return {"calibrated": False, "looking": False, "ready_for_calibration": True,
                    "message": "Please look directly at the camera"}
        looking = self.is_looking_at_camera(landmarks, w, h)
        if not self.calibrated:
            return {"looking": bool(looking), "ready_for_calibration": bool(self._pre_cal_check(landmarks, w, h))}
        return {"looking": bool(looking)}


detector = None
detector_lock = threading.Lock()
_detectors_by_sid: dict[str, EyeContactDetector_Callib] = {}


def get_head_tracking_detector(sid: str | None = None):
    global detector
    from flask import request

    session_id = sid or getattr(request, "sid", None)
    if session_id:
        with detector_lock:
            existing = _detectors_by_sid.get(session_id)
            if existing is not None:
                return existing
            try:
                _detectors_by_sid[session_id] = EyeContactDetector_Callib()
                print(f"[INFO] Head tracking initialized for session {session_id}")
                return _detectors_by_sid[session_id]
            except Exception as e:
                print(f"[ERROR] Head tracking failed for session {session_id}: {e}")
                return None

    if detector is not None:
        return detector
    with detector_lock:
        if detector is not None:
            return detector
        try:
            detector = EyeContactDetector_Callib()
            print("[INFO] Head tracking initialized (legacy singleton)")
        except Exception as e:
            print(f"[ERROR] Head tracking failed: {e}")
            detector = None
    return detector


def decode_image(img_data):
    try:
        if "," not in img_data:
            raise ValueError("Bad image data")
        _, encoded = img_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        img = Image.open(io.BytesIO(img_bytes))
        cv2 = get_cv2()
        np = get_numpy()
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"decode_image error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  WHISPER (speech-to-text)
# ─────────────────────────────────────────────────────────────────────────────

whisper_model = None

def initialize_whisper():
    global whisper_model
    if whisper_model is not None:
        return
    from faster_whisper import WhisperModel

    model_size = optional_env("WHISPER_MODEL", "base")
    inference_device = get_inference_device()
    whisper_device = "cpu" if inference_device == "mps" else inference_device
    print(f"[INFO] Loading Whisper {model_size} on {whisper_device}...")
    try:
        whisper_model = WhisperModel(model_size, device=whisper_device)
        print("[INFO] Whisper ready")
    except Exception as e:
        print(f"[ERROR] Whisper load failed: {e}")
        whisper_model = None

def reinitialize_whisper():
    global whisper_model
    try:
        del whisper_model
        whisper_model = None
    except Exception:
        pass
    initialize_whisper()
    return whisper_model is not None

def convert_to_wav(input_path):
    wav_path = input_path + "_converted.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", wav_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return wav_path
    except FileNotFoundError:
        print("[ERROR] ffmpeg is not installed on this server")
        return None
    except subprocess.CalledProcessError:
        return None

def is_blank_audio(audio_path, rms_threshold=0.005):
    try:
        sf = get_soundfile()
        np = get_numpy()
        audio, _ = sf.read(audio_path)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return np.sqrt(np.mean(audio**2)) < rms_threshold
    except Exception:
        return False

def _transcribe(wav_path):
    beam_size = max(1, int(optional_env("WHISPER_BEAM_SIZE", "1")))
    segs, info = whisper_model.transcribe(wav_path, beam_size=beam_size, language="en", task="transcribe")
    return " ".join(s.text for s in list(segs))

def process_audio_file(file, auth_header=None, *, _local_only=False):
    return stt_transcribe_file(
        file,
        auth_header=auth_header,
        local_only=_local_only,
        convert_to_wav=convert_to_wav,
        is_blank_audio=is_blank_audio,
    )


def schedule_background_ai_warmup():
    if optional_env("ENABLE_AI_WARMUP", "false").lower() in {"0", "false", "no"}:
        return

    def _warmup():
        try:
            initialize_whisper()
        except Exception as exc:
            print(f"[WARN] Whisper warmup skipped: {exc}")
        try:
            get_head_tracking_detector()
        except Exception as exc:
            print(f"[WARN] Head tracking warmup skipped: {exc}")

    threading.Thread(target=_warmup, name="ai-warmup", daemon=True).start()

# ─────────────────────────────────────────────────────────────────────────────
#  HEALTH
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/health/live', methods=['GET'])
def health_live():
    from common.health import live_payload

    return jsonify(live_payload()), 200


@app.route('/api/health/ready', methods=['GET'])
def health_ready():
    from common.health import ready_payload

    payload = ready_payload()
    return jsonify(payload), 200 if payload.get("ready") else 503


@app.route('/api/health', methods=['GET'])
def health_check():
    from common.health import full_health_payload

    payload = full_health_payload()
    return jsonify(payload), 200


@app.route('/api/service-hours', methods=['GET'])
def service_hours():
    return jsonify({"success": True, "data": service_hours_status()}), 200


EMPTY_UPLOAD_READABLE_MESSAGE = (
    "The uploaded resume appears to be empty or missing enough relevant information. Please upload a valid resume."
)


def extract_text_from_uploaded_document(file_path, ext):
    ext = ext.lower()
    if ext == 'txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as handle:
            return handle.read()
    if ext == 'pdf':
        import PyPDF2
        from PyPDF2.errors import EmptyFileError
        text = []
        try:
            with open(file_path, 'rb') as handle:
                reader = PyPDF2.PdfReader(handle)
                for page in reader.pages:
                    text.append(page.extract_text() or "")
        except EmptyFileError:
            raise ValueError(EMPTY_UPLOAD_READABLE_MESSAGE) from None
        return "\n".join(text)
    if ext == 'docx':
        try:
            import docx
            document = docx.Document(file_path)
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        except ModuleNotFoundError:
            import zipfile
            from xml.etree import ElementTree

            with zipfile.ZipFile(file_path) as archive:
                xml_bytes = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml_bytes)
            namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paragraphs = []
            for paragraph in root.findall(".//w:p", namespace):
                text_parts = [node.text for node in paragraph.findall(".//w:t", namespace) if node.text]
                if text_parts:
                    paragraphs.append("".join(text_parts))
            return "\n".join(paragraphs)
    if ext == 'doc':
        if textract is not None:
            extracted = textract.process(file_path)
            return extracted.decode('utf-8', errors='ignore')
        raise RuntimeError("Legacy .doc parsing is not available on this server. Please upload .docx, .pdf, or .txt.")
    raise RuntimeError(f"Unsupported file type: {ext}")


def _guess_job_title_from_lines(lines):
    """Deterministic title guess from extracted JD lines (no LLM)."""
    for line in lines[:12]:
        normalized = line.lower()
        if 2 <= len(line) <= 120 and any(keyword in normalized for keyword in [
            'engineer', 'developer', 'manager', 'analyst', 'consultant', 'specialist',
            'architect', 'lead', 'qa', 'tester', 'intern', 'administrator', 'devops',
            'sre', 'support', 'designer', 'scientist'
        ]):
            return line
    return (lines[0][:120] if lines else "")


def summarize_job_description_text(raw_text):
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    text = "\n".join(lines).strip()
    if not text:
        return {"job_title": "", "job_description": ""}

    title = _guess_job_title_from_lines(lines)
    compact_description = " ".join(segment.strip() for segment in lines[:40])
    compact_description = compact_description[:4000].strip()

    return {
        "job_title": title,
        "job_description": compact_description,
    }


def extract_job_description_from_file_text(raw_text):
    """
    File-upload path: keep extracted text as-is (no LLM polish) so content_hash stays stable.
    Only guess a title heuristically for the title tab.
    """
    text = (raw_text or "").strip()
    if not text:
        return {
            "job_title": "",
            "job_description": "",
            "is_technical": False,
            "parser": "extract",
        }

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    job_title = _guess_job_title_from_lines(lines)
    is_technical = classify_job_description_is_technical(job_title, text)
    return {
        "job_title": job_title,
        "job_description": text,
        "is_technical": is_technical,
        "parser": "extract",
    }


def validate_job_description_text(job_description, min_chars=30, min_words=6, min_alpha_ratio=0.45):
    from common.document_validation import validate_job_description_extracted_text
    return validate_job_description_extracted_text(job_description)


def validate_resume_text(resume_text):
    from common.document_validation import validate_resume_text as _validate_resume_text
    return _validate_resume_text(resume_text)


def classify_job_description_is_technical(job_title, job_description):
    from common.role_classification import classify_job_description_is_technical as _classify
    return _classify(job_title, job_description)


def get_ollama_model_name():
    return (optional_env("OLLAMA_MODEL", "llama3") or "llama3").strip()


def _normalize_model_aliases(name: str):
    normalized = (name or "").strip().lower()
    if not normalized:
        return set()
    base = normalized.split(":", 1)[0]
    return {normalized, base}


def _fetch_ollama_diagnostics(timeout_seconds=2):
    health_url = optional_env("OLLAMA_HEALTH_URL", "http://127.0.0.1:11434/api/tags")
    configured_model = get_ollama_model_name()
    diagnostics = {
        "health_url": health_url,
        "model": configured_model,
        "reachable": False,
        "status_code": None,
        "model_available": False,
        "ready": False,
        "available_models": [],
        "error": "",
    }

    try:
        response = http_requests.get(health_url, timeout=timeout_seconds)
        diagnostics["status_code"] = response.status_code
        diagnostics["reachable"] = response.ok
        if not response.ok:
            diagnostics["error"] = f"Health endpoint returned HTTP {response.status_code}"
            return diagnostics

        payload = response.json() if response.content else {}
        models = payload.get("models") if isinstance(payload, dict) else []
        names = []
        if isinstance(models, list):
            for item in models:
                if not isinstance(item, dict):
                    continue
                name = (item.get("name") or "").strip()
                if name:
                    names.append(name)
        diagnostics["available_models"] = names

        configured_aliases = _normalize_model_aliases(configured_model)
        available_aliases = set()
        for name in names:
            available_aliases.update(_normalize_model_aliases(name))
        diagnostics["model_available"] = bool(configured_aliases & available_aliases)
        diagnostics["ready"] = diagnostics["reachable"] and diagnostics["model_available"]
        if diagnostics["reachable"] and not diagnostics["model_available"]:
            diagnostics["error"] = f"Configured model '{configured_model}' is not installed in Ollama."
        return diagnostics
    except Exception as exc:
        diagnostics["error"] = str(exc)
        return diagnostics


def get_ollama_diagnostics(timeout_seconds=2):
    ttl = max(5.0, float(optional_env("OLLAMA_DIAGNOSTICS_CACHE_SECONDS", "30")))

    def _fetch():
        if llm_provider_name() == "ollama":
            return _fetch_ollama_diagnostics(timeout_seconds=timeout_seconds)
        return get_llm_diagnostics()

    return cached(
        f"ollama_diag:{timeout_seconds}",
        ttl,
        _fetch,
    )


def _env_int(name, default):
    try:
        return int(optional_env(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


QUESTION_GEN_OLLAMA_TIMEOUT_SECONDS = _env_int("QUESTION_GEN_OLLAMA_TIMEOUT_SECONDS", 90)
GENERATE_ANSWERS_TIMEOUT_SECONDS = _env_int("GENERATE_ANSWERS_TIMEOUT_SECONDS", 300)
JD_PARSE_OLLAMA_TIMEOUT_SECONDS = _env_int("JD_PARSE_OLLAMA_TIMEOUT_SECONDS", 25)
INTERVIEW_RESPONSE_TIMEOUT_SECONDS = _env_int("INTERVIEW_RESPONSE_TIMEOUT_SECONDS", 45)


def _env_truthy(name, default="false"):
    return (optional_env(name, default) or default).strip().lower() in {"1", "true", "yes", "on"}


def _parse_job_description_with_ollama(extracted_text, temp_path):
    """Parse JD via Ollama; fall back to heuristic extraction on failure."""
    try:
        llm_result = _run_callable_with_timeout(
            lambda: _parse_job_description_file(temp_path, model=get_ollama_model_name()),
            JD_PARSE_OLLAMA_TIMEOUT_SECONDS,
            label="Job description parsing",
        )
        job_title = (llm_result.get("job_title") or "").strip()
        job_description = (llm_result.get("job_description") or "").strip()
        if not job_title or not job_description:
            raise ValueError("Ollama returned empty job title or description")

        is_technical = classify_job_description_is_technical(job_title, job_description)
        try:
            is_technical = _run_callable_with_timeout(
                lambda: _classify_if_technical_role(
                    job_title, job_description, model=get_ollama_model_name()
                ),
                10,
                label="Technical role classification",
            )
        except Exception as classify_error:
            print(f"[WARN] LLM technical classification failed, using heuristic fallback: {classify_error}")

        return {
            "job_title": job_title,
            "job_description": job_description,
            "is_technical": is_technical,
            "parser": "ollama",
        }
    except Exception as llm_error:
        print(f"[WARN] Ollama JD parse failed, using heuristic fallback: {llm_error}")
        local_result = summarize_job_description_text(extracted_text)
        job_title = (local_result.get("job_title") or "").strip()
        job_description = (local_result.get("job_description") or "").strip()
        is_technical = classify_job_description_is_technical(job_title, job_description)
        return {
            "job_title": job_title,
            "job_description": job_description,
            "is_technical": is_technical,
            "parser": "local_fallback",
        }


def _run_callable_with_timeout(fn, timeout_seconds, label="operation"):
    future = _TIMEOUT_EXECUTOR.submit(fn)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError as exc:
        raise TimeoutError(f"{label} timed out after {timeout_seconds}s") from exc


def _parse_job_description_file(path, model=None):
    from INTERVIEW.jd_parser import parse_job_description_file

    return parse_job_description_file(path, model=model)


def _classify_if_technical_role(job_title, job_description, model=None):
    from INTERVIEW.jd_parser import classify_if_technical_role

    return classify_if_technical_role(job_title, job_description, model=model)


def _question_generation_error_status(exc):
    message = str(exc)
    if isinstance(exc, TimeoutError) or "timed out after" in message.lower():
        return 504
    if "not available" in message.lower() or "not installed" in message.lower():
        return 503
    return 500


def _ollama_diagnostic_snapshot():
    diagnostics = get_ollama_diagnostics(timeout_seconds=3)
    lines = [
        f"ready={diagnostics.get('ready')}",
        f"reachable={diagnostics.get('reachable')}",
        f"status_code={diagnostics.get('status_code')}",
        f"model={diagnostics.get('model')}",
        f"model_available={diagnostics.get('model_available')}",
        f"health_url={diagnostics.get('health_url')}",
    ]
    if diagnostics.get("available_models"):
        lines.append("available_models=" + ", ".join(diagnostics["available_models"]))
    if diagnostics.get("error"):
        lines.append(f"error={diagnostics['error']}")
    return {
        "available": True,
        "path": "ollama diagnostics",
        "lines": lines,
        "summary": diagnostics,
    }

# ─────────────────────────────────────────────────────────────────────────────
#  AUTH  (replaces the legacy hosted auth layer)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/signup', methods=['POST', 'OPTIONS'])
@rate_limit(max_calls=5, window_seconds=60)
def signup():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    try:
        username = normalize_username(data.get('username', ''))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    try:
        user = execute(
            """
            INSERT INTO users (username, email, password_hash, full_name)
            VALUES (%s, %s, %s, %s)
            RETURNING {columns}
            """.format(columns=build_user_columns(_USER_PUBLIC_FIELDS)),
            (username, email, hash_password(password), full_name)
        )
        verification_payload = issue_email_verification(user, allow_manual_fallback=True)
        return jsonify({
            "user": serialize_user(user),
            **verification_payload,
        }), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as e:
        message = str(e).lower()
        if 'idx_users_username_unique' in message or 'username' in message and 'unique' in message:
            return jsonify({"error": "Username is already taken"}), 409
        if 'email' in message and 'unique' in message:
            return jsonify({"error": "Email already registered"}), 409
        print(f"[ERROR] signup: {e}")
        return jsonify({"error": "Signup failed"}), 500


@app.route('/api/login', methods=['POST', 'OPTIONS'])
@rate_limit(max_calls=10, window_seconds=60)
def login():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    identifier = data.get('identifier', data.get('email', '')).strip().lower()
    password = data.get('password', '')
    user = get_user_for_auth(identifier)
    if not user or not check_password(password, user['password_hash']):
        return jsonify({"error": "Invalid credentials"}), 401
    if not user.get('email_verified_at'):
        return jsonify({
            "error": "Please verify your email before logging in.",
            "verification_required": True,
            "email": user['email'],
        }), 403
    token = create_token(str(user['id']), user['email'], user['full_name'], user['plan'])
    return _issue_auth_response({"user": serialize_user(user)}, token)


@app.route('/api/check-email', methods=['POST', 'OPTIONS'])
@rate_limit(max_calls=20, window_seconds=60)
def check_email():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    user = query_one("SELECT id FROM users WHERE email = %s", (email,))
    return jsonify({"exists": user is not None})


@app.route('/api/check-username', methods=['POST', 'OPTIONS'])
@rate_limit(max_calls=20, window_seconds=60)
def check_username():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    try:
        username = normalize_username(data.get('username', ''))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    user = query_one("SELECT id FROM users WHERE lower(coalesce(username, '')) = %s", (username,))
    return jsonify({"exists": user is not None})


@app.route('/api/resend-verification', methods=['POST', 'OPTIONS'])
@rate_limit(max_calls=5, window_seconds=300)
def resend_verification():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({"error": "Email is required"}), 400
    user = query_one(
        """
        SELECT {columns}
        FROM users WHERE lower(email) = %s
        """.format(columns=build_user_columns(_USER_PUBLIC_FIELDS)),
        (email,),
    )
    if not user:
        return jsonify({
            "message": "If an account exists, a verification email has been sent.",
        }), 200
    if user.get('email_verified_at'):
        return jsonify({"message": "Email already verified"}), 200
    try:
        verification_payload = issue_email_verification(user, allow_manual_fallback=True)
        return jsonify(verification_payload), 200
    except Exception as exc:
        print(f"[ERROR] resend_verification: {exc}")
        return jsonify({"error": "Unable to send verification email"}), 500


@app.route('/api/verify-email', methods=['GET'])
def verify_email():
    token = request.args.get('token', '').strip()
    if not token:
        return jsonify({"error": "Verification token is required"}), 400
    token_hash = hash_verification_token(token)
    record = query_one(
        """
        SELECT evt.user_id, {columns}
        FROM email_verification_tokens evt
        JOIN users u ON u.id = evt.user_id
        WHERE evt.token_hash = %s AND evt.consumed_at IS NULL AND evt.expires_at > now()
        """.format(columns=build_user_columns(_USER_PUBLIC_FIELDS, "u")),
        (token_hash,),
    )
    if not record:
        return jsonify({"error": "Verification link is invalid or expired"}), 400
    execute("UPDATE email_verification_tokens SET consumed_at = now() WHERE token_hash = %s", (token_hash,))
    user = execute(
        """
        UPDATE users
        SET email_verified_at = COALESCE(email_verified_at, now())
        WHERE id = %s
        RETURNING {columns}
        """.format(columns=build_user_columns(_USER_PUBLIC_FIELDS)),
        (record['user_id'],),
    )
    token_value = create_token(str(user['id']), user['email'], user['full_name'], user['plan'])
    return _issue_auth_response({
        "message": "Email verified successfully.",
        "user": serialize_user(user),
    }, token_value)


@app.route('/api/me', methods=['GET'])
@verify_auth_token
def get_me():
    user = query_one(
        "SELECT {columns} FROM users WHERE id = %s".format(columns=build_user_columns(_USER_PUBLIC_FIELDS)),
        (request.user['id'],),
    )
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": serialize_user(user)})


@app.route('/api/me/avatar', methods=['GET', 'OPTIONS'])
@app.route('/functions/v1/me/avatar', methods=['GET', 'OPTIONS'])
@verify_auth_token
def get_my_avatar():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200

    user = query_one(
        "SELECT avatar_url FROM users WHERE id = %s",
        (request.user['id'],),
    )
    if not user:
        return jsonify({"error": "User not found"}), 404

    avatar_url = (user.get('avatar_url') or '').strip()
    relative = resolve_relative_path(avatar_url)
    if not relative or not user_owns_storage_path(request.user['id'], relative):
        abort(404)

    clean_path = validated_protected_relative_path(relative)
    if not clean_path or not safe_storage_file_path(clean_path):
        abort(404)

    return send_storage_file(clean_path)

# ─────────────────────────────────────────────────────────────────────────────
#  RESUME UPLOAD  (replaces the legacy storage layer)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/upload-resume', methods=['POST', 'OPTIONS'])
@verify_auth_token
def upload_resume():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({"success": False, "message": "Empty filename"}), 400
    user_id = request.user['id']
    ext = secure_filename(file.filename).rsplit('.', 1)[-1].lower()
    if ext not in ['pdf', 'doc', 'docx', 'txt']:
        return jsonify({"success": False, "message": "File type not allowed"}), 400
    import uuid
    file_bytes = file.read()
    content_hash = hash_resume_bytes(file_bytes)
    filename = f"{uuid.uuid4()}.{ext}"
    folder = f"resumes/{user_id}"
    result = save_bytes(file_bytes, folder, filename)
    resume = execute(
        "INSERT INTO resumes (user_id, file_url, file_name, stored_path, content_hash) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id, file_url, file_name, content_hash",
        (user_id, result['public_url'], file.filename, result['relative_path'], content_hash)
    )
    return jsonify({"success": True, "data": {
        "resume_id": str(resume['id']),
        "url": result['public_url'],
        "path": result['relative_path'],
        "file_name": file.filename,
        "content_hash": content_hash,
    }})

# ─────────────────────────────────────────────────────────────────────────────
#  JOB DESCRIPTIONS  (implements the app API)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/job-descriptions', methods=['POST', 'OPTIONS'])
@verify_auth_token
def create_job_description():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    jd_description = (data.get('description') or "").strip()
    is_valid_jd, jd_validation_error = validate_job_description_text(jd_description)
    if not is_valid_jd:
        return jsonify({"success": False, "message": jd_validation_error}), 400
    title = (data.get('title') or "").strip()
    content_hash = hash_job_description(title, jd_description)
    jd = execute(
        "INSERT INTO job_descriptions (user_id, title, description, technical, content_hash) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING *",
        (request.user['id'], title, jd_description, data.get('technical', True), content_hash)
    )
    return jsonify({"success": True, "data": dict(jd)}), 201


@app.route('/api/job-descriptions', methods=['GET'])
@verify_auth_token
def get_job_descriptions():
    rows = query_all("SELECT * FROM job_descriptions WHERE user_id=%s ORDER BY created_at DESC",
                     (request.user['id'],))
    return jsonify({"success": True, "data": [dict(r) for r in rows]})


@app.route('/api/check-resume-jd-pair', methods=['POST', 'OPTIONS'])
@verify_auth_token
def check_resume_jd_pair():
    """
    Detect existing resume+JD pair for this user via content hash (+ filename gate).
    Multipart: file + job_title + job_description
    JSON: skills_text + job_title + job_description (+ optional file_name)
    """
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200

    user_id = request.user['id']
    job_title = (request.form.get('job_title') or (request.get_json(silent=True) or {}).get('job_title') or "").strip()
    job_description = (
        request.form.get('job_description')
        or (request.get_json(silent=True) or {}).get('job_description')
        or ""
    ).strip()
    if not job_title or not job_description:
        return jsonify({
            "success": False,
            "message": "job_title and job_description are required",
        }), 400

    data_json = request.get_json(silent=True) or {}
    skills_text = (request.form.get('skills_text') or data_json.get('skills_text') or "").strip()
    incoming_file_name = (request.form.get('file_name') or data_json.get('file_name') or "").strip()

    resume_hash = None
    filename_match = False
    content_match_resume = False
    resume_id = None
    resume_url = None

    if 'file' in request.files and request.files['file'] and request.files['file'].filename:
        upload = request.files['file']
        file_bytes = upload.read()
        resume_hash = hash_resume_bytes(file_bytes)
        incoming_file_name = incoming_file_name or (upload.filename or "").strip()
    elif skills_text:
        resume_hash = hash_skills_text(skills_text)
        incoming_file_name = ""
    else:
        return jsonify({
            "success": False,
            "message": "Provide a resume file or skills_text",
        }), 400

    jd_hash = hash_job_description(job_title, job_description)

    if incoming_file_name:
        name_row = query_one(
            """
            SELECT id, file_url, content_hash, file_name
            FROM resumes
            WHERE user_id=%s AND lower(file_name)=lower(%s)
            ORDER BY uploaded_at DESC NULLS LAST
            LIMIT 1
            """,
            (user_id, incoming_file_name),
        )
        if name_row:
            filename_match = True

    hash_resume_row = query_one(
        """
        SELECT id, file_url, content_hash, file_name
        FROM resumes
        WHERE user_id=%s AND content_hash=%s
        ORDER BY uploaded_at DESC NULLS LAST
        LIMIT 1
        """,
        (user_id, resume_hash),
    ) if resume_hash else None
    if hash_resume_row:
        content_match_resume = True
        resume_id = str(hash_resume_row['id'])
        resume_url = hash_resume_row.get('file_url')

    jd_row = query_one(
        """
        SELECT id, title, content_hash
        FROM job_descriptions
        WHERE user_id=%s AND content_hash=%s
        ORDER BY created_at DESC NULLS LAST
        LIMIT 1
        """,
        (user_id, jd_hash),
    )
    jd_id = str(jd_row['id']) if jd_row else None
    content_match_jd = bool(jd_row)
    content_match = bool(content_match_resume and content_match_jd)

    questions_exist = False
    question_set_count = 0
    latest_question_set = None
    if resume_id and jd_id:
        q_stats = query_one(
            """
            SELECT COUNT(DISTINCT question_set) AS set_count,
                   MAX(question_set) AS latest_set
            FROM questions
            WHERE resume_id=%s AND jd_id=%s
            """,
            (resume_id, jd_id),
        )
        if q_stats:
            question_set_count = int(q_stats.get('set_count') or 0)
            latest_question_set = q_stats.get('latest_set')
            questions_exist = question_set_count > 0

    return jsonify({
        "success": True,
        "match": {
            "resume_id": resume_id,
            "jd_id": jd_id,
            "resume_url": resume_url,
            "resume_hash": resume_hash,
            "jd_hash": jd_hash,
            "filename_match": filename_match,
            "content_match": content_match,
            "content_match_resume": content_match_resume,
            "content_match_jd": content_match_jd,
            "questions_exist": questions_exist and content_match,
            "question_set_count": question_set_count,
            "latest_question_set": latest_question_set,
            "job_title": job_title,
        },
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
#  INTERVIEWS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/interview-quota', methods=['GET', 'OPTIONS'])
@verify_auth_token
def get_interview_quota():
    return interview_quota_handler()


@app.route('/api/interviews/start', methods=['POST', 'OPTIONS'])
@verify_auth_token
def start_interview():
    return start_interview_handler()


@app.route('/api/interviews', methods=['POST', 'OPTIONS'])
@verify_auth_token
def create_interview():
    return start_interview_handler()


@app.route('/api/interviews', methods=['GET'])
@verify_auth_token
def get_interviews():
    rows = query_all("SELECT * FROM interviews WHERE user_id=%s ORDER BY scheduled_at DESC",
                     (request.user['id'],))
    return jsonify({"success": True, "data": [dict(r) for r in rows]})


@app.route('/api/interviews/<interview_id>', methods=['PUT', 'OPTIONS'])
@verify_auth_token
def update_interview(interview_id):
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    execute("UPDATE interviews SET status=%s WHERE id=%s AND user_id=%s",
            (data.get('status', 'ACTIVE'), interview_id, request.user['id']))
    return jsonify({"success": True})


def _interview_timer_response(interview_id: str, user_id: str, action: str):
    row = query_one(
        "SELECT id, status, active_seconds FROM interviews WHERE id=%s AND user_id=%s",
        (interview_id, user_id),
    )
    if not row:
        return jsonify({"success": False, "message": "Interview not found"}), 404
    if row.get("status") != "STARTED":
        return jsonify({
            "success": True,
            "data": {"active_seconds": int(row.get("active_seconds") or 0)},
        })
    if action == "tick":
        active_seconds = tick_interview_time(interview_id, user_id)
    else:
        active_seconds = pause_interview_time(interview_id, user_id)
    return jsonify({"success": True, "data": {"active_seconds": active_seconds}})


@app.route('/api/interviews/<interview_id>/timer-tick', methods=['POST', 'OPTIONS'])
@app.route('/functions/v1/interviews/<interview_id>/timer-tick', methods=['POST', 'OPTIONS'])
@app.route('/api/functions/v1/interviews/<interview_id>/timer-tick', methods=['POST', 'OPTIONS'])
@verify_auth_token
def interview_timer_tick(interview_id):
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    return _interview_timer_response(interview_id, request.user['id'], "tick")


@app.route('/api/interviews/<interview_id>/timer-pause', methods=['POST', 'OPTIONS'])
@app.route('/functions/v1/interviews/<interview_id>/timer-pause', methods=['POST', 'OPTIONS'])
@app.route('/api/functions/v1/interviews/<interview_id>/timer-pause', methods=['POST', 'OPTIONS'])
@verify_auth_token
def interview_timer_pause(interview_id):
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    return _interview_timer_response(interview_id, request.user['id'], "pause")

# ─────────────────────────────────────────────────────────────────────────────
#  INTERVIEW DATA  (implements the app API interview-data)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/interview-data', methods=['GET'])
@verify_auth_token
def get_interview_data():
    interview_id = request.args.get('interview_id')
    interview = query_one(
        "SELECT i.*, jd.title, jd.description FROM interviews i "
        "LEFT JOIN job_descriptions jd ON jd.id = i.jd_id WHERE i.id=%s AND i.user_id=%s",
        (interview_id, request.user['id'])
    )
    if not interview:
        return jsonify({"success": False, "message": "Interview not found"}), 404
    questions = query_all("SELECT * FROM questions WHERE interview_id=%s ORDER BY created_at",
                          (interview_id,))
    return jsonify({"success": True, "data": {
        "job_description": {
            "title": interview['title'],
            "description": interview['description']
        },
        "questions": [dict(q) for q in questions]
    }})

# ─────────────────────────────────────────────────────────────────────────────
#  QUESTIONS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/questions', methods=['POST', 'OPTIONS'])
@verify_auth_token
def save_questions():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    interview_id = data.get('interview_id')
    questions = data.get('questions', [])
    saved = []
    for q in questions:
        exp = normalize_difficulty_experience(q.get("difficulty_experience"))
        level = normalize_question_difficulty(q.get('difficulty_category') or q.get('difficulty_level'))
        row = execute(
            "INSERT INTO questions (interview_id, resume_id, jd_id, question_text, expected_answer, "
            "difficulty_level, difficulty_experience, question_set, requires_code) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (interview_id, data.get('resume_id'), data.get('jd_id'),
             q.get('question_text'), q.get('expected_answer'),
             level, exp, q.get('question_set', 1),
             q.get('requires_code', False))
        )
        saved.append(str(row['id']))
    return jsonify({"success": True, "data": {"saved": len(saved)}}), 201


@app.route('/api/questions/<interview_id>', methods=['GET'])
@verify_auth_token
def get_questions(interview_id):
    rows = query_all(f"SELECT * FROM questions WHERE interview_id=%s ORDER BY {QUESTION_ORDER_SQL}", (interview_id,))
    return jsonify({"success": True, "data": [dict(r) for r in rows]})

# ─────────────────────────────────────────────────────────────────────────────
#  TRANSCRIPTS  (implements the app API)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/transcripts', methods=['POST', 'OPTIONS'])
@verify_auth_token
def save_transcript():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    execute(
        "INSERT INTO transcripts (interview_id, full_transcript, evaluation_data) "
        "VALUES (%s,%s,%s) ON CONFLICT (interview_id) DO UPDATE "
        "SET full_transcript=EXCLUDED.full_transcript, evaluation_data=EXCLUDED.evaluation_data",
        (data['interview_id'], data.get('full_transcript'), json.dumps(data.get('evaluation_data')))
    )
    return jsonify({"success": True}), 201


@app.route('/api/transcripts/<interview_id>', methods=['GET'])
@verify_auth_token
def get_transcript(interview_id):
    row = query_one("SELECT * FROM transcripts WHERE interview_id=%s", (interview_id,))
    if not row:
        return jsonify({"success": False, "message": "Not found"}), 404
    return jsonify({"success": True, "data": dict(row)})

# ─────────────────────────────────────────────────────────────────────────────
#  INTERVIEW FEEDBACK  (implements the app API)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/interview-feedback', methods=['POST', 'OPTIONS'])
@verify_auth_token
def save_feedback():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    execute(
        "INSERT INTO interview_feedback (interview_id, summary, key_strengths, improvement_areas, metrics, audio_url) "
        "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (interview_id) DO UPDATE "
        "SET summary=EXCLUDED.summary, key_strengths=EXCLUDED.key_strengths, "
        "improvement_areas=EXCLUDED.improvement_areas, metrics=EXCLUDED.metrics, audio_url=EXCLUDED.audio_url",
        (data['interview_id'], data.get('summary'),
         json.dumps(data.get('key_strengths')), json.dumps(data.get('improvement_areas')),
         json.dumps(data.get('metrics')), data.get('audio_url'))
    )
    return jsonify({"success": True}), 201


@app.route('/api/interview-feedback/<interview_id>', methods=['GET'])
@verify_auth_token
def get_feedback(interview_id):
    row = query_one(
        """
        SELECT f.*, i.active_seconds, i.ended_at
        FROM interview_feedback f
        JOIN interviews i ON i.id = f.interview_id
        WHERE f.interview_id=%s AND i.user_id=%s
        """,
        (interview_id, request.user['id']),
    )
    if not row:
        return jsonify({"success": False, "message": "Not found"}), 404
    return jsonify({"success": True, "data": normalize_feedback_row(row)})

# ─────────────────────────────────────────────────────────────────────────────
#  CHAT HISTORY
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/chat-history/<interview_id>', methods=['GET'])
@verify_auth_token
def get_chat_history(interview_id):
    rows = query_all("SELECT * FROM chat_history WHERE interview_id=%s ORDER BY created_at", (interview_id,))
    return jsonify({"success": True, "data": [dict(r) for r in rows]})

# ─────────────────────────────────────────────────────────────────────────────
#  DASHBOARD  (implements the app API dashboard)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/dashboard', methods=['GET'])
@verify_auth_token
def dashboard():
    user_id = request.user['id']
    page  = max(1, int(request.args.get('page', 1)))
    limit = min(50, max(1, int(request.args.get('limit', 20))))
    offset = (page - 1) * limit

    total_row = query_one("SELECT COUNT(*) AS cnt FROM interviews WHERE user_id=%s", (user_id,))
    total_interviews = int(total_row['cnt']) if total_row else 0

    interviews = query_all(
        "SELECT i.*, jd.title as job_title FROM interviews i "
        "LEFT JOIN job_descriptions jd ON jd.id=i.jd_id "
        "WHERE i.user_id=%s ORDER BY i.scheduled_at DESC LIMIT %s OFFSET %s",
        (user_id, limit, offset)
    )
    interview_ids = [str(r['id']) for r in interviews]
    feedbacks = []
    if interview_ids:
        placeholders = ','.join(['%s'] * len(interview_ids))
        feedbacks = query_all(
            f"SELECT f.* FROM interview_feedback f WHERE f.interview_id IN ({placeholders})",
            tuple(interview_ids)
        )
    return jsonify({
        "success": True,
        "data": {
            "interviews": [dict(r) for r in interviews],
            "feedbacks": [dict(r) for r in feedbacks],
            "total_interviews": total_interviews,
            "page": page,
            "limit": limit,
            "total_pages": max(1, -(-total_interviews // limit))
        }
    })

# ─────────────────────────────────────────────────────────────────────────────
#  PARSE JOB DESCRIPTION FILE
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/parse-job-description', methods=['POST', 'OPTIONS'])
@verify_auth_token
def parse_job_description():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    if 'file' not in request.files:
        data = request.get_json(silent=True) or {}
        job_title = (data.get('job_title') or '').strip()
        job_description = (data.get('job_description') or '').strip()
        if job_title and job_description:
            is_valid_jd, jd_validation_error = validate_job_description_text(job_description)
            if not is_valid_jd:
                return jsonify({"success": False, "message": jd_validation_error}), 400
            is_technical = classify_job_description_is_technical(job_title, job_description)
            try:
                is_technical = _run_callable_with_timeout(
                    lambda: _classify_if_technical_role(
                        job_title, job_description, model=get_ollama_model_name()
                    ),
                    30,
                    label="Technical role classification",
                )
            except Exception as classify_error:
                print(f"[WARN] LLM technical classification failed, using keyword fallback: {classify_error}")
            return jsonify({
                "success": True,
                "message": "Job description accepted",
                "data": {
                    "job_title": job_title,
                    "job_description": job_description,
                    "is_technical": is_technical,
                    "parser": "manual",
                },
            })
        return jsonify({"success": False, "message": "No file uploaded"}), 400
    file = request.files['file']
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ['pdf', 'txt', 'doc', 'docx']:
        return jsonify({"success": False, "message": "Unsupported file type"}), 400
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tf:
            file.save(tf.name)
            temp_path = tf.name
        try:
            try:
                extracted_text = extract_text_from_uploaded_document(temp_path, ext)
            except ValueError as ve:
                return jsonify({"success": False, "message": str(ve)}), 400
            is_valid_jd, jd_validation_error = validate_job_description_text(extracted_text)
            if not is_valid_jd:
                return jsonify({"success": False, "message": jd_validation_error}), 400

            # File upload: raw extract only (no LLM polish) so JD content_hash is stable.
            # Paste / URL flows keep their existing LLM paths.
            parsed = extract_job_description_from_file_text(extracted_text)
            return jsonify({"success": True, "data": {
                "job_title": parsed["job_title"],
                "job_description": parsed["job_description"],
                "is_technical": parsed["is_technical"],
                "parser": parsed.get("parser", "extract"),
            }})
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/extract-job-from-url', methods=['POST', 'OPTIONS'])
@verify_auth_token
def extract_job_from_url_api():
    """Fetch a job posting URL and extract job title + description."""
    safe_error_message = (
        "We couldn't fetch this job description from the link. "
        "Please paste it manually or upload the JD file."
    )
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200

    try:
        data = request.get_json() or {}
        url = (data.get('url') or '').strip()

        if not url:
            return jsonify({
                "success": False,
                "message": safe_error_message
            }), 400

        print(f"[DEBUG] Extracting job from URL: {url}")

        from INTERVIEW.jd_parser import extract_job_from_url

        try:
            result = extract_job_from_url(url, model=get_ollama_model_name())
        except Exception as e:
            print(f"[ERROR] URL extraction failed: {e}")
            traceback.print_exc()
            return jsonify({
                "success": False,
                "message": safe_error_message
            }), 500

        job_title = (result.get('job_title') or '').strip()
        job_description = (result.get('job_description') or '').strip()
        job_responsibilities = (result.get('job_responsibilities') or '').strip()
        requires_manual_paste = bool(result.get("requires_manual_paste"))
        warning_message = (result.get("warning_message") or "").strip()

        if not job_title and not job_description and not job_responsibilities:
            return jsonify({
                "success": False,
                "message": safe_error_message
            }), 400

        combined_description = job_description
        if job_responsibilities:
            if combined_description:
                combined_description += "\n\nResponsibilities:\n" + job_responsibilities
            else:
                combined_description = "Responsibilities:\n" + job_responsibilities

        is_technical = False
        if job_title and combined_description:
            is_technical = classify_job_description_is_technical(job_title, combined_description)
            try:
                is_technical = _run_callable_with_timeout(
                    lambda: _classify_if_technical_role(
                        job_title, combined_description, model=get_ollama_model_name()
                    ),
                    10,
                    label="Technical role classification",
                )
            except Exception as classify_error:
                print(f"[WARN] Failed to classify technical role for URL job: {classify_error}")

        return jsonify({
            "success": True,
            "message": "Job extracted from URL successfully",
            "data": {
                "job_title": job_title,
                "job_description": combined_description,
                "responsibilities": job_responsibilities,
                "is_technical": is_technical,
                "requires_manual_paste": requires_manual_paste,
                "warning_message": warning_message
            }
        })

    except Exception as e:
        print(f"[ERROR] General error in extract_job_from_url_api: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": safe_error_message
        }), 500


@app.route('/api/classify-technical-role', methods=['POST', 'OPTIONS'])
@verify_auth_token
def classify_technical_role():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    job_title = data.get('job_title', '').strip()
    job_description = data.get('job_description', '').strip()
    if not job_title or not job_description:
        return jsonify({"success": False, "message": "job_title and job_description required"}), 400
    is_valid_jd, jd_validation_error = validate_job_description_text(job_description)
    if not is_valid_jd:
        return jsonify({"success": False, "message": jd_validation_error}), 400
    try:
        is_technical = classify_job_description_is_technical(job_title, job_description)
        try:
            is_technical = _run_callable_with_timeout(
                lambda: _classify_if_technical_role(
                    job_title, job_description, model=get_ollama_model_name()
                ),
                10,
                label="Technical role classification",
            )
        except Exception as classify_error:
            print(f"[WARN] LLM technical classification failed, using keyword fallback: {classify_error}")
        return jsonify({"success": True, "is_technical": is_technical})
    except Exception as e:
        return jsonify({"success": False, "message": str(e), "is_technical": False}), 500

# ─────────────────────────────────────────────────────────────────────────────
#  GENERATE QUESTIONS FROM RESUME
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/generate-questions', methods=['POST', 'OPTIONS'])
@app.route('/api/api/generate-questions', methods=['POST', 'OPTIONS'])
@verify_auth_token
def generate_questions():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    try:
        data = request.get_json() or {}
        resume_url = data.get('resume_url')
        skills_text = data.get('skills_text')
        job_description = (data.get('job_description') or "").strip()
        job_title = (data.get('job_title') or "").strip()
        resume_id = data.get('resume_id')
        jd_id = data.get('jd_id')

        if not job_title or not job_description:
            return jsonify({
                "success": False,
                "message": "Missing required fields: job_title and job_description",
            }), 400
        if resume_url and skills_text:
            return jsonify({
                "success": False,
                "message": "Provide either resume_url or skills_text, not both",
            }), 400
        if not resume_url and not skills_text:
            return jsonify({
                "success": False,
                "message": "Missing required field: provide either resume_url or skills_text (comma-separated skills)",
            }), 400
        if skills_text and (not resume_id or not jd_id):
            return jsonify({
                "success": False,
                "message": "When using skills_text, resume_id and jd_id are required for saving questions",
            }), 400

        is_valid_jd, jd_validation_error = validate_job_description_text(job_description)
        if not is_valid_jd:
            return jsonify({"success": False, "message": jd_validation_error}), 400

        skills_list = None
        if skills_text:
            skills_list = [s.strip() for s in (skills_text or "").split(",") if s and s.strip()]
            if not skills_list:
                return jsonify({
                    "success": False,
                    "message": "Please provide at least one skill in skills_text (comma-separated)",
                }), 400
            if len(skills_list) > 10:
                return jsonify({
                    "success": False,
                    "message": "Please provide at most 10 skills.",
                }), 400
            print(f"[DEBUG] Skills-based profile: {len(skills_list)} skills")

        question_counts = data.get('question_counts', {'beginner': 2, 'medium': 2, 'hard': 2})
        ollama_diagnostics = get_ollama_diagnostics(timeout_seconds=3)
        pipeline_kwargs = {
            "resume_path": None,
            "job_title": job_title,
            "job_description": job_description,
            "question_counts": question_counts,
            "include_answers": data.get("include_answers", False),
            "split": data.get("split", False),
            "resume_pct": data.get("resume_pct", 50),
            "jd_pct": data.get("jd_pct", 50),
            "blend": data.get("blend", False),
            "blend_pct_resume": data.get("blend_pct_resume", 50),
            "blend_pct_jd": data.get("blend_pct_jd", 50),
            "max_retries": 2,
            "skills_list": skills_list,
            "resume_id": resume_id,
            "jd_id": jd_id,
            "user_id": request.user["id"],
        }

        temp_resume = None
        if resume_url:
            relative = resolve_relative_path(resume_url)
            if relative:
                resume_data = read_bytes(relative)
                ext = relative.rsplit('.', 1)[-1]
            else:
                resp = http_requests.get(resume_url)
                resp.raise_for_status()
                resume_data = resp.content
                ext = resume_url.split('.')[-1].lower() or 'pdf'

            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tf:
                tf.write(resume_data)
                temp_resume = tf.name

            try:
                resume_text = extract_text_from_uploaded_document(temp_resume, ext)
            except ValueError as ve:
                return jsonify({"success": False, "message": str(ve)}), 400
            is_valid_resume, resume_validation_error = validate_resume_text(resume_text)
            if not is_valid_resume:
                return jsonify({"success": False, "message": resume_validation_error}), 400
            pipeline_kwargs["resume_path"] = temp_resume

        try:
            from INTERVIEW.question_generation import run_pipeline_from_api
            try:
                result = _run_callable_with_timeout(
                    lambda: run_pipeline_from_api(**pipeline_kwargs),
                    QUESTION_GEN_OLLAMA_TIMEOUT_SECONDS,
                    label="Question generation pipeline",
                )
            except Exception as pipeline_error:
                print(
                    "[ERROR] Ollama question generation failed: "
                    f"{pipeline_error} | ollama={json.dumps(ollama_diagnostics)}"
                )
                status = _question_generation_error_status(pipeline_error)
                return jsonify({
                    "success": False,
                    "message": str(pipeline_error),
                    "debug": {
                        "generator": "ollama_failed",
                        "ollama": ollama_diagnostics,
                    },
                }), status
            if not result.get("success") or not result.get("questions"):
                error_message = result.get("error") or "Pipeline returned no questions"
                print(
                    "[ERROR] Ollama question generation failed: "
                    f"{error_message} | ollama={json.dumps(ollama_diagnostics)}"
                )
                return jsonify({
                    "success": False,
                    "message": error_message,
                    "debug": {
                        "generator": "ollama_failed",
                        "ollama": ollama_diagnostics,
                    },
                }), 500
            result.setdefault("generator", "ollama_pipeline")
            result["ollama_diagnostics"] = ollama_diagnostics
            return jsonify({"success": True, "data": {
                "questions": result['questions'],
                "questions_count": result['questions_count'],
                "candidate_name": result['candidate']
            }, "debug": {
                "generator": result.get("generator", "unknown"),
                "answer_generation": result.get("answer_generation", {}),
                "token_usage": result.get("token_usage", {}),
                "ollama": result.get("ollama_diagnostics", ollama_diagnostics),
            }})
        finally:
            if temp_resume and os.path.exists(temp_resume):
                os.unlink(temp_resume)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/generate-answers', methods=['POST', 'OPTIONS'])
@app.route('/api/api/generate-answers', methods=['POST', 'OPTIONS'])
@verify_auth_token
def generate_answers_for_question_set():
    """Generate one best sample answer per question (dossier-backed batch)."""
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    try:
        data = request.get_json() or {}
        resume_id = data.get("resume_id")
        jd_id = data.get("jd_id")
        question_set = data.get("question_set")

        if not resume_id or not jd_id or question_set is None:
            return jsonify({
                "success": False,
                "message": "resume_id, jd_id, and question_set are required",
            }), 400

        user_id = request.user["id"]
        resume_row = query_one(
            "SELECT * FROM resumes WHERE id=%s AND user_id=%s",
            (resume_id, user_id),
        )
        if not resume_row:
            return jsonify({"success": False, "message": "Resume not found"}), 404

        jd_row = query_one(
            "SELECT * FROM job_descriptions WHERE id=%s AND user_id=%s",
            (jd_id, user_id),
        )
        if not jd_row:
            return jsonify({"success": False, "message": "Job description not found"}), 404

        question_set = int(question_set)
        existing = query_all(
            """
            SELECT * FROM questions
            WHERE resume_id=%s AND jd_id=%s AND question_set=%s
            ORDER BY created_at ASC
            """,
            (resume_id, jd_id, question_set),
        )
        if not existing:
            return jsonify({
                "success": False,
                "message": f"No questions found for question set {question_set}",
            }), 404

        job_title = (jd_row.get("title") or "").strip()

        from INTERVIEW.dossier_store import load_dossier
        from INTERVIEW.answer_generation import (
            _dedupe_question_rows,
            run_generate_answers_for_question_set,
        )

        dossier = load_dossier(resume_id, jd_id, user_id=user_id)
        if not dossier:
            return jsonify({
                "success": False,
                "message": (
                    "Interview dossier not found for this resume and job description. "
                    "Regenerate questions for this pair first, then generate sample answers."
                ),
            }), 404

        dossier_cache = "hit"
        existing_rows = [dict(row) for row in existing]
        unique_rows = _dedupe_question_rows(existing_rows)
        if not unique_rows:
            return jsonify({
                "success": False,
                "message": "No questions found to generate answers for",
            }), 404

        ollama_diagnostics = get_ollama_diagnostics(timeout_seconds=3)
        try:
            result = _run_callable_with_timeout(
                lambda: run_generate_answers_for_question_set(
                    dossier=dossier,
                    question_rows=unique_rows,
                    model=get_ollama_model_name(),
                    job_title=job_title,
                    dossier_cache=dossier_cache,
                ),
                GENERATE_ANSWERS_TIMEOUT_SECONDS,
                label="Sample answer generation",
            )
        except Exception as pipeline_error:
            print(
                "[ERROR] Sample answer generation failed: "
                f"{pipeline_error} | ollama={json.dumps(ollama_diagnostics)}"
            )
            status = _question_generation_error_status(pipeline_error)
            return jsonify({
                "success": False,
                "message": str(pipeline_error),
                "debug": {"ollama": ollama_diagnostics},
            }), status

        if not result.get("success"):
            return jsonify({
                "success": False,
                "message": result.get("error") or "Answer generation failed",
            }), 500

        generated = result.get("questions") or []
        if not generated:
            return jsonify({
                "success": False,
                "message": "Answer generation returned no questions",
            }), 500

        saved = []
        for question in generated:
            qid = question.get("id")
            answer = question.get("expected_answer") or question.get("answer") or ""
            q_text = (question.get("question_text") or question.get("question") or "").strip()
            level = normalize_question_difficulty(
                question.get("difficulty_category") or question.get("difficulty_level")
            )
            if not qid:
                continue
            row = execute(
                """
                UPDATE questions
                SET expected_answer=%s
                WHERE id=%s AND resume_id=%s AND jd_id=%s AND question_set=%s
                RETURNING *
                """,
                (answer, qid, resume_id, jd_id, question_set),
            )
            if not row and q_text:
                # Fallback: match by text+level if id was synthetic
                row = execute(
                    """
                    UPDATE questions
                    SET expected_answer=%s
                    WHERE id = (
                        SELECT id FROM questions
                        WHERE resume_id=%s AND jd_id=%s AND question_set=%s
                          AND lower(question_text)=lower(%s)
                          AND lower(coalesce(difficulty_level, '')) = lower(%s)
                        ORDER BY created_at ASC
                        LIMIT 1
                    )
                    RETURNING *
                    """,
                    (answer, resume_id, jd_id, question_set, q_text, level),
                )
            if row:
                saved.append(_serialize_question(row))

                # Delete legacy duplicate rows (same text+level, different answer-depth rows)
                execute(
                    """
                    DELETE FROM questions
                    WHERE resume_id=%s AND jd_id=%s AND question_set=%s
                      AND lower(question_text)=lower(%s)
                      AND lower(coalesce(difficulty_level, '')) = lower(%s)
                      AND id <> %s
                    """,
                    (resume_id, jd_id, question_set, q_text or row.get("question_text"), level, row["id"]),
                )

        if not saved:
            return jsonify({
                "success": False,
                "message": "Failed to save sample answers to the database",
            }), 500

        saved.sort(key=_question_sort_key)
        return jsonify({
            "success": True,
            "data": {
                "questions": saved,
                "questions_count": len(saved),
            },
            "debug": {
                "answer_generation": result.get("answer_generation", {}),
                "ollama": ollama_diagnostics,
                "dossier_cache": dossier_cache,
            },
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# ─────────────────────────────────────────────────────────────────────────────
#  TRANSCRIBE AUDIO
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/internal/transcribe-audio', methods=['POST'])
def transcribe_audio_internal():
    """Whisper-only endpoint for TRANSCRIBE_SERVICE_URL forwarding (token required)."""
    expected = (optional_env("TRANSCRIBE_INTERNAL_TOKEN", "") or "").strip()
    if not expected or request.headers.get("X-Internal-Token") != expected:
        return jsonify({"success": False, "message": "Forbidden"}), 403
    if "audio" not in request.files:
        return jsonify({"success": False, "message": "No audio file"}), 400
    result = process_audio_file(request.files["audio"], _local_only=True)
    if not result.get("success"):
        return jsonify({"success": False, "message": result.get("error")}), 500
    return jsonify({"success": True, "transcription": result.get("transcription", "")})


@app.route('/api/transcribe-audio', methods=['POST', 'OPTIONS'])
@app.route('/api/api/transcribe-audio', methods=['POST', 'OPTIONS'])
@verify_auth_token
@user_rate_limit(max_calls=30, window_seconds=60)
def transcribe_audio():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    if 'audio' not in request.files:
        return jsonify({"success": False, "message": "No audio file"}), 400
    file = request.files['audio']
    result = process_audio_file(file, auth_header=request.headers.get("Authorization"))
    if not result.get('success'):
        return jsonify({"success": False, "message": result.get('error')}), 500
    transcription = result.get('transcription', '')

    # Optionally save audio file
    if transcription:
        try:
            user_id = request.user['id']
            interview_id = request.args.get('interview_id') or request.form.get('interview_id')
            if user_id and interview_id:
                ts = datetime.now().strftime("%Y%m%dT%H%M%S")
                file.seek(0)
                save_bytes(file.read(), f"audio/{user_id}/{interview_id}", f"user_{ts}.wav")
        except Exception as e:
            print(f"[WARN] Audio save skipped: {e}")

    return jsonify({"success": True, "data": {
        "transcription": transcription,
        "word_count": len(transcription.split()) if transcription else 0
    }})

# ─────────────────────────────────────────────────────────────────────────────
#  GENERATE RESPONSE  (main interview AI loop)
# ─────────────────────────────────────────────────────────────────────────────

def _build_core_questions_list(questions_rows):
    seen = {}
    for q in questions_rows:
        question_text = (q.get('question_text') or '').strip()
        if not question_text:
            continue
        key = question_text.lower()
        if key not in seen:
            seen[key] = {
                "question_text": question_text,
                "requires_code": bool(q.get('requires_code', False)),
                "difficulty_level": normalize_question_difficulty(
                    q.get('difficulty_level') or q.get('difficulty_category')
                ),
            }
    return list(seen.values())


def _fetch_interview_question_rows(interview_row, interview_id, user_id):
    questions_rows = query_all(
        f"SELECT * FROM questions WHERE interview_id=%s ORDER BY {QUESTION_ORDER_SQL}",
        (interview_id,),
    )
    if (
        not questions_rows
        and interview_row.get('resume_id')
        and interview_row.get('jd_id')
        and interview_row.get('question_set') is not None
    ):
        questions_rows = query_all(
            f"""
            SELECT q.*
            FROM questions q
            JOIN resumes r ON r.id = q.resume_id
            JOIN job_descriptions jd ON jd.id = q.jd_id
            WHERE q.resume_id=%s
              AND q.jd_id=%s
              AND q.question_set=%s
              AND r.user_id=%s
              AND jd.user_id=%s
            ORDER BY {QUESTION_ORDER_SQL_Q_ALIAS}
            """,
            (
                interview_row['resume_id'],
                interview_row['jd_id'],
                int(interview_row['question_set']),
                user_id,
                user_id,
            ),
        )
    return questions_rows


_END_INTERVIEW_LATER_STAGES = frozenset({
    "custom_questions",
    "candidate_questions",
    "wrapup_evaluation",
    "manual_end",
    "timeout",
})


def _interview_session_ui_state(interview_id: str, user_id: str) -> dict:
    """Restore interview UI flags from the persisted manager session."""
    saved_state = load_session(f"{interview_id}:{user_id}")
    if not saved_state:
        return {
            "interview_stage": "introduction",
            "has_answered_resume_question": False,
            "can_end_interview": False,
        }

    stage = str(saved_state.get("stage") or "introduction")
    has_answered = bool(str(saved_state.get("last_resume_response") or "").strip())
    if not has_answered:
        for entry in saved_state.get("evaluation_log") or []:
            if isinstance(entry, dict) and entry.get("stage") == "resume":
                has_answered = True
                break

    can_end = stage in _END_INTERVIEW_LATER_STAGES or (
        stage == "resume_discussion" and has_answered
    )
    return {
        "interview_stage": stage,
        "has_answered_resume_question": has_answered,
        "can_end_interview": can_end,
    }


def _interview_dynamic_config(interview_row, interview_id, user_id, saved_state):
    if saved_state:
        cached_id = saved_state.get('_config_interview_id')
        cached_config = saved_state.get('_dynamic_config')
        if cached_id == interview_id and isinstance(cached_config, dict):
            config = dict(cached_config)
            config["time_limit_minutes"] = 0
            return config

    questions_rows = _fetch_interview_question_rows(interview_row, interview_id, user_id)
    return {
        "job_title": interview_row.get('title') or '',
        "job_description": interview_row.get('description') or '',
        "core_questions": _build_core_questions_list(questions_rows),
        "coding_requirement": [],
        "time_limit_minutes": 0,
        "custom_questions": [],
    }


def _build_generate_response_payload(user, data, on_token=None):
    user_input = data.get('message', '').strip()
    interview_id = data.get('interview_id')

    # Fetch interview data directly (no loopback HTTP call)
    interview_row = query_one(
        "SELECT i.*, jd.title, jd.description FROM interviews i "
        "LEFT JOIN job_descriptions jd ON jd.id = i.jd_id WHERE i.id=%s AND i.user_id=%s",
        (interview_id, user['id'])
    )
    if not interview_row:
        return {"success": False, "message": "Interview not found"}, 404

    user_id = user['id']
    instance_key = f"{interview_id}:{user_id}"
    saved_state = load_session(instance_key)
    dynamic_config = _interview_dynamic_config(
        interview_row, interview_id, user_id, saved_state
    )

    manager = InterviewManager.from_config(dynamic_config)
    if saved_state:
        manager.__dict__.update({
            k: v for k, v in saved_state.items()
            if not callable(v) and k not in ('model', 'time_limit_seconds')
        })
    manager.time_limit_seconds = 0

    tracked_active_seconds = tick_interview_time(interview_id, user_id)
    manager.tracked_active_seconds = tracked_active_seconds

    try:
        def _receive():
            return manager.receive_input(user_input, on_token=on_token)

        response = _run_callable_with_timeout(
            _receive,
            INTERVIEW_RESPONSE_TIMEOUT_SECONDS,
            label="Interview response",
        )
    except Exception as interview_error:
        print(f"[WARN] Interview manager timed out or failed: {interview_error}")
        response = {
            "stage": getattr(manager, "stage", "introduction"),
            "message": (
                "Thanks for your answer. The AI is taking longer than usual — "
                "please continue, or use End interview when you are ready."
            ),
        }

    # Persist updated session state
    try:
        serializable = {
            k: v for k, v in manager.__dict__.items()
            if isinstance(v, (str, int, float, bool, list, dict, type(None)))
        }
        serializable['_config_interview_id'] = interview_id
        serializable['_dynamic_config'] = dynamic_config
        timer_session = load_session(instance_key) or {}
        if TIMER_LAST_TICK_KEY in timer_session:
            serializable[TIMER_LAST_TICK_KEY] = timer_session[TIMER_LAST_TICK_KEY]
        save_session(instance_key, serializable)
    except Exception as se:
        print(f"[WARN] Session save failed: {se}")

    chat_rows = [(interview_id, 'user', user_input)]
    if response.get("message"):
        chat_rows.append((interview_id, 'assistant', response["message"]))
    execute_many(
        "INSERT INTO chat_history (interview_id, role, content) VALUES (%s,%s,%s)",
        chat_rows,
    )

    # Generate Piper audio for interviewer response (Classic server voice only)
    audio_url = None
    server_tts_enabled = _env_truthy("INTERVIEW_SERVER_TTS", "false")
    if (
        response.get("message")
        and not response.get("interview_done", False)
        and server_tts_enabled
    ):
        try:
            response_text = response["message"]
            ts = datetime.now().strftime("%Y%m%dT%H%M%S")
            text_hash = hashlib.sha256(response_text.encode()).hexdigest()[:8]
            filename = f"interviewer_{text_hash}_{ts}.wav"
            folder = f"audio/{user_id}/{interview_id}"

            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tf2:
                temp_audio = tf2.name
            audio_path = synthesize_text_to_wav(response_text, temp_audio)
            with open(audio_path, 'rb') as af:
                audio_data = af.read()
            storage_result = save_bytes(audio_data, folder, filename)
            audio_url = storage_result['public_url']
            if os.path.exists(temp_audio):
                os.unlink(temp_audio)
        except Exception as ae:
            print(f"[WARN] Audio generation failed: {ae}")
        finally:
            pass

    # Handle timeout (flag from InterviewManager)
    if response.get("timeout_detected", False):
        response["interview_done"] = True

    # Handle interview completion - direct DB writes, no loopback HTTP
    feedback_saved = False
    if response.get("interview_done", False):
        merged_path = None
        merged_url = None
        try:
            merged_path = _merge_interview_audio(user_id, interview_id)
            merged_url = public_url(merged_path) if merged_path else None
        except Exception as audio_exc:
            print(f"[WARN] Audio merge failed; saving text feedback without merged audio: {audio_exc}")

        try:
            # Save transcript directly
            execute(
                "INSERT INTO transcripts (interview_id, full_transcript, evaluation_data) "
                "VALUES (%s, %s, %s) ON CONFLICT (interview_id) DO UPDATE "
                "SET full_transcript=EXCLUDED.full_transcript, evaluation_data=EXCLUDED.evaluation_data",
                (interview_id,
                 json.dumps(manager.conversation_history),
                 json.dumps(getattr(manager, 'final_evaluation_log', None)))
            )

            # Save feedback directly
            execute(
                "INSERT INTO interview_feedback (interview_id, summary, key_strengths, improvement_areas, metrics, audio_url) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (interview_id) DO UPDATE "
                "SET summary=EXCLUDED.summary, key_strengths=EXCLUDED.key_strengths, "
                "improvement_areas=EXCLUDED.improvement_areas, metrics=EXCLUDED.metrics, audio_url=EXCLUDED.audio_url",
                (interview_id,
                 getattr(manager, 'final_summary', None),
                 format_feedback_text(getattr(manager, 'key_strengths', [])),
                 format_feedback_text(getattr(manager, 'improvement_areas', [])),
                 json.dumps(getattr(manager, 'metrics', {})),
                 merged_url)
            )

            finalize_interview_time(interview_id, user_id)
            execute("UPDATE interviews SET status='ENDED' WHERE id=%s", (interview_id,))

            # Remove session from store
            delete_session(instance_key)
            feedback_saved = True
        except Exception as se:
            print(f"[ERROR] Save on completion failed: {se}")

        # Clean up per-turn audio files only after feedback has been persisted.
        if feedback_saved and merged_path:
            try:
                audio_folder = build_protected_storage_path("audio", user_id, interview_id)
                if audio_folder:
                    per_turn = [f for f in list_folder(audio_folder)
                                if f['name'].startswith(('interviewer_', 'user_'))]
                    delete_files([f['relative_path'] for f in per_turn])
            except Exception as cleanup_exc:
                print(f"[WARN] Audio cleanup failed after feedback save: {cleanup_exc}")

    return {
        "success": True,
        "data": {
            "response": response.get("message", "Sorry, something went wrong."),
            "stage": response.get("stage", "unknown"),
            "interview_done": response.get("interview_done", False),
            "feedback_saved_successfully": feedback_saved,
            "audio_url": _serialize_file_url(audio_url),
            "should_delete_audio": False,
            "requires_code": response.get("requires_code"),
            "code_language": response.get("code_language"),
        },
    }, 200


@app.route('/api/generate-response', methods=['POST'])
@verify_auth_token
@user_rate_limit(max_calls=60, window_seconds=60)
def generate_response():
    try:
        data = request.get_json() or {}
        if not data.get('message', '').strip():
            return jsonify({"success": False, "message": "Message required"}), 400
        if not data.get('interview_id'):
            return jsonify({"success": False, "message": "interview_id required"}), 400

        with interview_turn_slot():
            payload, status_code = _build_generate_response_payload(request.user, data)
        return jsonify(payload), status_code
    except InterviewCapacityError as exc:
        return jsonify({
            "success": False,
            "busy": True,
            "message": str(exc),
            "retry_after": exc.retry_after,
        }), 503
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/generate-response-stream', methods=['POST'])
@verify_auth_token
@user_rate_limit(max_calls=60, window_seconds=60)
def generate_response_stream():
    data = request.get_json() or {}

    def sse_events():
        yield "event: started\ndata: {}\n\n"
        try:
            if not data.get('message', '').strip():
                err = {"success": False, "message": "Message required"}
                yield f"event: error\ndata: {json.dumps(err)}\n\n"
                return
            if not data.get('interview_id'):
                err = {"success": False, "message": "interview_id required"}
                yield f"event: error\ndata: {json.dumps(err)}\n\n"
                return
            event_q = queue.Queue()
            user = request.user

            def on_token(text):
                if text:
                    event_q.put(("token", {"text": text}))

            def worker():
                try:
                    with interview_turn_slot() as slot:
                        if slot and slot.get("queue_position", 0) > 0:
                            event_q.put((
                                "queued",
                                {"position": slot["queue_position"], "message": "Waiting for AI capacity…"},
                            ))
                        payload, _status = _build_generate_response_payload(
                            user, data, on_token=on_token
                        )
                    event_q.put(("complete", payload))
                except InterviewCapacityError as exc:
                    event_q.put(("error", {
                        "success": False,
                        "busy": True,
                        "message": str(exc),
                        "retry_after": exc.retry_after,
                    }))
                except Exception as exc:
                    traceback.print_exc()
                    event_q.put(("error", {"success": False, "message": str(exc)}))

            threading.Thread(target=worker, daemon=True).start()
            while True:
                kind, payload = event_q.get()
                yield f"event: {kind}\ndata: {json.dumps(payload)}\n\n"
                if kind in ("complete", "error"):
                    break
        except InterviewCapacityError as exc:
            err = {
                "success": False,
                "busy": True,
                "message": str(exc),
                "retry_after": exc.retry_after,
            }
            yield f"event: error\ndata: {json.dumps(err)}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'success': False, 'message': str(exc)})}\n\n"

    return Response(
        stream_with_context(sse_events()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# ─────────────────────────────────────────────────────────────────────────────
#  AUDIO MERGE HELPER
# ─────────────────────────────────────────────────────────────────────────────
def _audio_turn_timestamp(filename):
    """Extract YYYYMMDDTHHMMSS from user_* or interviewer_*_*.wav for chronological merge."""
    match = re.search(r'(\d{8}T\d{6})', filename or '')
    return match.group(1) if match else filename

def _merge_interview_audio(user_id, interview_id):
    folder = build_protected_storage_path("audio", user_id, interview_id)
    if not folder:
        return None
    files = list_folder(folder)
    if not files:
        return None
    audio_files = [f for f in files if f['name'].startswith(('interviewer_', 'user_'))]
    if not audio_files:
        return None
    audio_files.sort(key=lambda x: _audio_turn_timestamp(x['name']))
    segments = []
    temp_files = []
    try:
        for f in audio_files:
            data = read_bytes(f['relative_path'])
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tf:
                tf.write(data)
                temp_files.append(tf.name)
            segments.append(get_pydub().from_wav(tf.name))
        if not segments:
            return None
        merged = segments[0]
        for s in segments[1:]:
            merged = merged + s
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as mf:
            merged.export(mf.name, format="wav")
            temp_files.append(mf.name)
            with open(mf.name, 'rb') as f:
                merged_data = f.read()
        result = save_bytes(merged_data, folder, f"audio_transcript_{interview_id}.wav")
        return result['relative_path']
    except Exception as e:
        print(f"[ERROR] Audio merge failed: {e}")
        return None
    finally:
        for t in temp_files:
            if os.path.exists(t):
                os.remove(t)

# ─────────────────────────────────────────────────────────────────────────────
#  GENERATE SPEECH (TTS)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/generate-speech', methods=['POST', 'OPTIONS'])
@verify_auth_token
def generate_speech():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"success": False, "message": "Text required"}), 400
    if len(text) > 1000:
        return jsonify({"success": False, "message": "Text too long (max 1000 chars)"}), 400
    try:
        user_id = request.user['id']
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        filename = f"tts_{ts}.wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tf:
            temp_path = tf.name
        audio_path = synthesize_text_to_wav(text, temp_path)
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        result = save_bytes(audio_data, f"audio/{user_id}/general", filename)
        os.unlink(temp_path)
        return jsonify({"success": True, "data": {
            "audio_url": result['protected_url'],
            "file_size": result['file_size']
        }})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# ─────────────────────────────────────────────────────────────────────────────
#  SUPPORT BOT
# ─────────────────────────────────────────────────────────────────────────────

def _load_support_faq_sections():
    faq_path = os.path.join(SUPPORT_BOT_PATH, "support_bot.md")
    sections = []
    current_title = None
    current_lines = []

    try:
        with open(faq_path, "r", encoding="utf-8") as faq_file:
            for line in faq_file:
                if line.startswith("## "):
                    if current_title:
                        sections.append((current_title, "".join(current_lines).strip()))
                    current_title = line.strip("# \n")
                    current_lines = []
                elif current_title:
                    current_lines.append(line)
        if current_title:
            sections.append((current_title, "".join(current_lines).strip()))
    except Exception as exc:
        print(f"[WARN] Unable to load support FAQ fallback: {exc}")

    return sections


def _support_bot_fallback_reply(user_message):
    sections = _load_support_faq_sections()
    if not sections:
        return (
            "I'm having trouble reaching the AI support service right now. "
            "Please try again in a moment, or contact support if the issue continues."
        ), []

    tokens = [token for token in re.findall(r"[a-z0-9]+", user_message.lower()) if len(token) > 2]
    scored = []
    for title, content in sections:
        haystack = f"{title}\n{content}".lower()
        score = sum(1 for token in tokens if token in haystack)
        scored.append((score, title, content))
    scored.sort(key=lambda item: item[0], reverse=True)
    best = [item for item in scored if item[0] > 0][:2] or scored[:1]
    title, content = best[0][1], best[0][2]
    compact = " ".join(content.split())
    if not compact:
        compact = "I found the related support topic, but it does not include detailed steps yet."
    return f"{title}: {compact[:700]}", [item[1] for item in best]


@app.route('/api/support-bot', methods=['POST', 'OPTIONS'])
@verify_auth_token
def support_bot():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({"success": False, "message": "Message required"}), 400
    try:
        from Support_manager_enhanced import SupportBotManager
        bot = SupportBotManager(
            model=get_ollama_model_name(),
            faq_path=os.path.join(SUPPORT_BOT_PATH, "support_bot.md")
        )
        auth = request.headers.get('Authorization')
        if auth:
            bot.set_auth_token(auth)
        response = bot.receive_input(user_message)
        return jsonify({"success": True, "data": {
            "response": response.get("message", "Sorry, I couldn't process your request."),
            "session_id": response.get("session_id"),
            "conversation_length": response.get("conversation_length", 0),
            "retrieved_sections": response.get("retrieved_sections", [])
        }})
    except Exception as e:
        traceback.print_exc()
        fallback_response, retrieved_sections = _support_bot_fallback_reply(user_message)
        return jsonify({"success": True, "data": {
            "response": fallback_response,
            "session_id": None,
            "conversation_length": 1,
            "retrieved_sections": retrieved_sections,
            "degraded": True
        }})

# ─────────────────────────────────────────────────────────────────────────────
#  PERFORMANCE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/analyze-performance-trends', methods=['POST', 'OPTIONS'])
@verify_auth_token
def analyze_performance_trends():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    try:
        if 'feedbacks' in data and isinstance(data['feedbacks'], list):
            result = analyze_performance_from_feedbacks(
                data['feedbacks'], data.get('model', get_ollama_model_name())
            )
        else:
            auth_token = request.headers.get('Authorization', '').split(' ')[-1]
            result = analyze_user_performance(
                auth_token, data.get('model', get_ollama_model_name()), data.get('limit', 100)
            )
        if not result.get('success'):
            return jsonify({"success": False, "message": result.get('error', 'Analysis failed')}), 400
        return jsonify({"success": True, "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/overall-performance', methods=['GET'])
@app.route('/api/api/overall-performance', methods=['GET'])
@verify_auth_token
def overall_performance():
    user_id = request.user['id']
    rows = query_all("SELECT * FROM overall_evaluation WHERE user_id=%s ORDER BY created_at DESC LIMIT 10",
                     (user_id,))
    return jsonify({"success": True, "data": [dict(r) for r in rows]})

# ─────────────────────────────────────────────────────────────────────────────
#  CODE EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

def _sandbox_preexec():
    """Apply resource limits before exec — Linux only."""
    try:
        import resource
        # Max CPU seconds
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        # Max output size 16 MB
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
        # Max RAM 256 MB
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        # Max open file descriptors
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        # No new processes
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    except Exception:
        pass  # Non-Linux platforms skip silently


_CODE_SIZE_LIMIT = 64 * 1024  # 64 KB

# Simple pattern blocklist for obviously dangerous code
import re as _re
_DANGER_PATTERNS = _re.compile(
    r'(import\s+os|import\s+subprocess|import\s+sys|'
    r'__import__|open\s*\(|exec\s*\(|eval\s*\(|'
    r'shutil|socket|requests|urllib|http\.client|'
    r'importlib|ctypes|threading|multiprocessing|'
    r'require\s*\(\s*[\'"]child_process|require\s*\(\s*[\'"]fs|'
    r'require\s*\(\s*[\'"]net|process\.|global\.|Function\s*\()',
    _re.IGNORECASE
)


def _run_code(cmd, code, suffix, timeout=8):
    if len(code) > _CODE_SIZE_LIMIT:
        return jsonify({"success": False, "message": "Code too large (max 64 KB)"}), 400
    if _DANGER_PATTERNS.search(code):
        return jsonify({"success": False, "message": "Blocked: dangerous module or function detected"}), 400
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
        f.write(code)
        path = f.name
    try:
        result = subprocess.run(
            cmd + [path],
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=_sandbox_preexec,
            env={"PATH": "/usr/bin:/usr/local/bin"}  # Stripped env
        )
        output = result.stdout[:50_000]  # Cap output at 50 KB
        error = result.stderr[:10_000] if result.returncode != 0 else None
        return jsonify({"success": True, "data": {"output": output, "error": error}})
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "message": "Code execution timed out (8s limit)"}), 408
    finally:
        if os.path.exists(path):
            os.unlink(path)


@app.route('/api/execute', methods=['POST', 'OPTIONS'])
@verify_auth_token
def execute_code():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    code = data.get('code', '').strip()
    language = data.get('language', 'python').lower()
    if not code:
        return jsonify({"success": False, "message": "No code provided"}), 400
    if language == 'javascript':
        return jsonify({
            "success": False,
            "message": "JavaScript execution is disabled for security reasons",
        }), 400
    try:
        if language == 'python':
            return _run_code(['python3'], code, '.py')
        elif language == 'java':
            with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False) as f:
                f.write(code); path = f.name
            try:
                if _DANGER_PATTERNS.search(code):
                    return jsonify({"success": False, "message": "Blocked: dangerous module or function detected"}), 400
                c = subprocess.run(
                    ['javac', path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    preexec_fn=_sandbox_preexec,
                    env={"PATH": "/usr/bin:/usr/local/bin"},
                )
                if c.returncode != 0:
                    return jsonify({"success": True, "data": {"output": "", "error": c.stderr}})
                cls = os.path.splitext(os.path.basename(path))[0]
                r = subprocess.run(
                    ['java', '-cp', os.path.dirname(path), cls],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    preexec_fn=_sandbox_preexec,
                    env={"PATH": "/usr/bin:/usr/local/bin"},
                )
                return jsonify({"success": True, "data": {"output": r.stdout, "error": r.stderr or None}})
            except subprocess.TimeoutExpired:
                return jsonify({"success": False, "message": "Timed out"}), 408
            finally:
                for p in [path, path.replace('.java', '.class')]:
                    if os.path.exists(p): os.unlink(p)
        else:
            return jsonify({"success": False, "message": f"Unsupported language: {language}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ─────────────────────────────────────────────────────────────────────────────
#  HEAD TRACKING SOCKETIO
# ─────────────────────────────────────────────────────────────────────────────

_socket_users = {}


@socketio.on('connect')
def handle_connect(auth):
    user = authenticate_socket_auth(auth)
    if not user:
        return False
    from flask import request as flask_request
    _socket_users[flask_request.sid] = user
    emit('response', {'message': 'Connected to head tracking'})


@socketio.on('disconnect')
def handle_disconnect():
    from flask import request as flask_request

    sid = getattr(flask_request, "sid", None)
    if sid:
        _socket_users.pop(sid, None)
        with detector_lock:
            _detectors_by_sid.pop(sid, None)
    print('Client disconnected')


def _require_socket_user():
    from flask import request as flask_request
    sid = getattr(flask_request, "sid", None)
    if not sid or sid not in _socket_users:
        emit("response", {"error": "Unauthorized"})
        return None
    return _socket_users[sid]


@socketio.on('frame')
def handle_frame(data):
    if not _require_socket_user():
        return
    try:
        img_data = data.get("image")
        calibrate = data.get("calibrate", False)
        if not img_data:
            emit("response", {"error": "No image data"})
            return
        frame = decode_image(img_data)
        if frame is None:
            emit("response", {"error": "Invalid image"})
            return
        detector_instance = get_head_tracking_detector()
        if detector_instance is None:
            emit("response", {"error": "Detector unavailable"})
            return
        result = detector_instance.process(frame, is_calibrating=calibrate)
        emit("response", result)
    except Exception as e:
        emit("response", {"error": str(e)})

@socketio.on('reset_calibration')
def handle_reset_calibration():
    if not _require_socket_user():
        return
    try:
        detector_instance = get_head_tracking_detector()
        if detector_instance is None:
            emit("response", {"error": "Detector unavailable"})
            return
        detector_instance.reset_calibration()
        emit("response", {"calibration_reset": True})
    except Exception as e:
        emit("response", {"error": str(e)})

# ─────────────────────────────────────────────────────────────────────────────
#  COMPATIBILITY HELPERS / LEGACY ROUTES
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_metrics(value):
    if isinstance(value, dict):
        return value
    if not value:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return None


def _normalize_list(value):
    def split_numbered_text(text):
        text = str(text).replace("\\n", "\n").strip()
        if not text:
            return []
        parts = re.split(r'\d+\.\s*', text)
        points = [part.strip(" \n\t-•") for part in parts if part.strip(" \n\t-•")]
        points = [part for part in points if not re.fullmatch(r'\d+', part)]
        if len(points) > 1:
            return points
        bullet_points = [part.strip(" \n\t-•") for part in re.split(r'\n\s*[-•]\s*', text) if part.strip(" \n\t-•")]
        return bullet_points or [text]

    if isinstance(value, list):
        normalized = []
        for item in value:
            normalized.extend(split_numbered_text(item) if isinstance(item, str) else [item])
        return normalized
    if not value:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                normalized = []
                for item in parsed:
                    normalized.extend(split_numbered_text(item) if isinstance(item, str) else [item])
                return normalized
            if isinstance(parsed, str):
                return split_numbered_text(parsed)
            if parsed is None:
                return []
            return [str(parsed)]
        except Exception:
            return split_numbered_text(value)
    return [value]


@app.route('/storage/<path:relative_path>', methods=['GET'])
def serve_storage_file(relative_path):
    """Legacy public storage route — disabled; use /api/files/ with JWT."""
    return jsonify({"error": "Direct storage access is not allowed. Use authenticated file API."}), 403


@app.route('/api/files/<path:relative_path>', methods=['GET', 'OPTIONS'])
@app.route('/functions/v1/files/<path:relative_path>', methods=['GET', 'OPTIONS'])
@app.route('/api/functions/v1/files/<path:relative_path>', methods=['GET', 'OPTIONS'])
@verify_auth_token
def download_protected_file(relative_path):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200

    clean_path = validated_protected_relative_path(relative_path)
    if not clean_path:
        return jsonify({"error": "Forbidden"}), 403

    if not user_owns_storage_path(request.user['id'], clean_path):
        return jsonify({"error": "Forbidden"}), 403

    if not safe_storage_file_path(clean_path):
        abort(404)

    return send_storage_file(clean_path)


@app.route('/api/delete-audio', methods=['DELETE', 'POST', 'OPTIONS'])
@verify_auth_token
def delete_audio_file():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200

    data = request.get_json(silent=True) or {}
    audio_url = data.get('audio_url', '').strip()
    if not audio_url:
        return jsonify({"success": False, "message": "audio_url required"}), 400

    relative = resolve_relative_path(audio_url)
    if not relative:
        return jsonify({"success": False, "message": "Invalid audio_url"}), 400
    if not relative.startswith(f"audio/{request.user['id']}/"):
        return jsonify({"success": False, "message": "Forbidden"}), 403
    if not safe_storage_file_path(relative):
        return jsonify({"success": True, "message": "Already deleted"})

    delete_files([relative])
    return jsonify({"success": True})


def _pairing_key(resume_id, jd_id):
    return f"{resume_id}:{jd_id}"


def _serialize_question(row):
    data = dict(row)
    difficulty = normalize_question_difficulty(data.get('difficulty_level') or data.get('difficulty_category'))
    data['difficulty_level'] = difficulty
    data['difficulty_category'] = difficulty
    data['difficulty_experience'] = normalize_difficulty_experience(data.get('difficulty_experience'))
    data['question'] = data.get('question_text')
    data['answer'] = data.get('expected_answer')
    return data


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _question_sort_key(row):
    difficulty_order = {"easy": 1, "medium": 2, "hard": 3}
    experience_order = {"beginner": 1, "intermediate": 2, "expert": 3}
    created_at = row.get('created_at')
    if isinstance(created_at, datetime):
        created_key = created_at.isoformat()
    else:
        created_key = str(created_at or '')
    return (
        -_safe_int(row.get('question_set')),
        difficulty_order.get(normalize_question_difficulty(row.get('difficulty_level') or row.get('difficulty_category')), 4),
        created_key,
        (row.get('question_text') or row.get('question') or '').strip().lower(),
        experience_order.get(normalize_difficulty_experience(row.get('difficulty_experience')), 4),
    )


def _build_dashboard_pairings(user_id):
    resumes = {
        str(row['id']): dict(row)
        for row in query_all(
            "SELECT id, file_url, file_name, stored_path, uploaded_at FROM resumes WHERE user_id=%s ORDER BY uploaded_at DESC",
            (user_id,)
        )
    }
    job_descriptions = {
        str(row['id']): dict(row)
        for row in query_all(
            "SELECT id, title, description, file_url, technical, created_at FROM job_descriptions WHERE user_id=%s ORDER BY created_at DESC",
            (user_id,)
        )
    }
    questions = [
        _serialize_question(row)
        for row in query_all(
            """
            SELECT q.*
            FROM questions q
            LEFT JOIN resumes r ON r.id = q.resume_id
            LEFT JOIN job_descriptions jd ON jd.id = q.jd_id
            WHERE COALESCE(r.user_id, jd.user_id) = %s
            ORDER BY q.created_at ASC
            """,
            (user_id,)
        )
    ]
    feedback_rows = {
        str(row['interview_id']): dict(row)
        for row in query_all(
            """
            SELECT f.*
            FROM interview_feedback f
            JOIN interviews i ON i.id = f.interview_id
            WHERE i.user_id = %s
            """,
            (user_id,),
        )
    }
    interviews = [
        dict(row)
        for row in query_all(
            "SELECT * FROM interviews WHERE user_id=%s ORDER BY scheduled_at DESC",
            (user_id,)
        )
    ]

    pairings = {}

    def ensure_pairing(resume_id, jd_id):
        if not resume_id or not jd_id:
            return None
        key = _pairing_key(resume_id, jd_id)
        if key not in pairings:
            resume = resumes.get(str(resume_id), {})
            jd = job_descriptions.get(str(jd_id), {})
            pairings[key] = {
                'id': key,
                'resume_id': str(resume_id),
                'jd_id': str(jd_id),
                'resumeName': resume.get('file_name', 'Resume'),
                'resumeUrl': _serialize_file_url(
                    resume.get('file_url') or (
                        protected_file_url(resume.get('stored_path', ''))
                        if resume.get('stored_path') else None
                    )
                ),
                'jobTitle': jd.get('title', 'Untitled role'),
                'jobDescription': jd.get('description', ''),
                'technical': jd.get('technical', True),
                'questionSets': {},
            }
        return pairings[key]

    for question in questions:
        pairing = ensure_pairing(question.get('resume_id'), question.get('jd_id'))
        if not pairing:
            continue
        set_number = int(question.get('question_set') or 1)
        pairing['questionSets'].setdefault(set_number, {
            'questionSetNumber': set_number,
            'questions': [],
            'interviews': [],
            'total_attempts': 0,
        })['questions'].append(question)

    for interview in interviews:
        pairing = ensure_pairing(interview.get('resume_id'), interview.get('jd_id'))
        if not pairing:
            continue
        set_number = int(interview.get('question_set') or 1)
        feedback = feedback_rows.get(str(interview['id']))
        metrics = _normalize_metrics(feedback.get('metrics') if feedback else None)
        pairing['questionSets'].setdefault(set_number, {
            'questionSetNumber': set_number,
            'questions': [],
            'interviews': [],
            'total_attempts': 0,
        })['interviews'].append({
            **interview,
            'metrics': metrics,
            'summary': feedback.get('summary') if feedback else None,
            'key_strengths': _normalize_list(feedback.get('key_strengths') if feedback else None),
            'improvement_areas': _normalize_list(feedback.get('improvement_areas') if feedback else None),
            'audio_url': _serialize_file_url(feedback.get('audio_url')) if feedback else None,
        })

    result = []
    for pairing in pairings.values():
        question_sets = []
        for set_number, set_data in sorted(pairing['questionSets'].items(), key=lambda item: item[0], reverse=True):
            interviews_for_set = sorted(
                set_data['interviews'],
                key=lambda row: row.get('attempt_number') or 0,
                reverse=True,
            )
            question_sets.append({
                'questionSetNumber': set_number,
                'questions': set_data['questions'],
                'interviews': interviews_for_set,
                'total_attempts': len(interviews_for_set),
            })
        pairing['questionSets'] = question_sets
        result.append(pairing)

    result.sort(key=lambda pairing: pairing['questionSets'][0]['questionSetNumber'] if pairing['questionSets'] else 0, reverse=True)
    return result


def _payment_redirect_url(interview_id, payment_id, resume_id=None, jd_id=None, question_set=None, status='success'):
    """Deprecated: internal stub redirect. Kept for backward compatibility references."""
    base = require_env("DOMAIN").rstrip('/')
    params = [f"checkout_intent_id={payment_id}"]
    if resume_id:
        params.append(f"resume_id={resume_id}")
    if jd_id:
        params.append(f"jd_id={jd_id}")
    if question_set is not None:
        params.append(f"question_set={question_set}")
    return f"{base}/payment-status?{'&'.join(params)}"


@app.route('/api/me', methods=['PUT', 'OPTIONS'])
@verify_auth_token
def update_me():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    data = request.get_json() or {}
    nested_data = data.get('data') or {}
    missing = object()
    updates = []
    params = []
    full_name = data['full_name'] if 'full_name' in data else nested_data.get('full_name', missing)
    username = data.get('username')
    nickname = data['nickname'] if 'nickname' in data else nested_data.get('nickname', missing)
    avatar_url = data['avatar_url'] if 'avatar_url' in data else nested_data.get('avatar_url', missing)
    date_of_birth = data['date_of_birth'] if 'date_of_birth' in data else nested_data.get('date_of_birth', missing)
    gender = data['gender'] if 'gender' in data else nested_data.get('gender', missing)
    password = data.get('password')
    try:
        if full_name is not missing:
            updates.append('full_name=%s')
            params.append(str(full_name).strip())
        if username is not None:
            username = normalize_username(username)
            updates.append('username=%s')
            params.append(username)
        if nickname is not missing:
            updates.append('nickname=%s')
            params.append(str(nickname).strip())
        if avatar_url is not missing:
            updates.append('avatar_url=%s')
            params.append(str(avatar_url or '').strip())
        if date_of_birth is not missing:
            updates.append('date_of_birth=%s')
            params.append(normalize_date_of_birth(date_of_birth))
        if gender is not missing:
            updates.append('gender=%s')
            params.append(normalize_gender(gender))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    if password:
        updates.append('password_hash=%s')
        params.append(hash_password(password))
    if not updates:
        user = query_one(
            'SELECT {columns} FROM users WHERE id=%s'.format(columns=build_user_columns(_USER_PUBLIC_FIELDS)),
            (request.user['id'],),
        )
        return jsonify({'success': True, 'user': serialize_user(user)})
    params.append(request.user['id'])
    try:
        user = execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id=%s RETURNING {build_user_columns(_USER_PUBLIC_FIELDS)}",
            tuple(params),
        )
    except Exception as exc:
        if 'idx_users_username_unique' in str(exc).lower():
            return jsonify({'error': 'Username is already taken'}), 409
        raise
    return jsonify({'success': True, 'user': serialize_user(user)})


@app.route('/api/resumes', methods=['GET', 'POST', 'OPTIONS'])
@verify_auth_token
def resumes_api():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    user_id = request.user['id']
    if request.method == 'GET':
        rows = query_all('SELECT * FROM resumes WHERE user_id=%s ORDER BY uploaded_at DESC', (user_id,))
        return jsonify({'success': True, 'data': [_serialize_resume_row(row) for row in rows]})
    data = request.get_json() or {}
    file_url = _serialize_file_url(data.get('file_url'))
    file_name = data.get('file_name') or 'resume'
    stored_path = data.get('stored_path')
    content_hash = (data.get('content_hash') or "").strip() or None
    if not content_hash and file_name.strip().lower() == 'skills-based profile':
        # Prefer hash from skills_text when provided by client
        skills_text = data.get('skills_text') or ""
        if skills_text:
            content_hash = hash_skills_text(skills_text)
        else:
            content_hash = hash_skills_list([])
    row = execute(
        'INSERT INTO resumes (user_id, file_url, file_name, stored_path, content_hash) '
        'VALUES (%s, %s, %s, %s, %s) RETURNING *',
        (user_id, file_url, file_name, stored_path, content_hash),
    )
    return jsonify({'success': True, 'data': dict(row)}), 201


@app.route('/api/payments', methods=['GET'])
@verify_auth_token
def get_payments():
    if request.args.get('get_all') == 'true' or request.path.startswith('/functions/'):
        pass  # same handler for legacy alias
    user_id = request.user['id']
    rows = query_all(
        """
        SELECT * FROM payments
        WHERE user_id = %s
        ORDER BY COALESCE(recorded_at, paid_at) DESC NULLS LAST
        """,
        (user_id,),
    )
    attempts = query_all(
        """
        SELECT
            ci.id AS checkout_intent_id,
            ci.status,
            ci.amount_paise AS amount,
            ci.created_at,
            ci.failure_reason
        FROM checkout_intents ci
        WHERE ci.user_id = %s
          AND ci.status IN ('failed', 'expired', 'checkout_creation_failed')
          AND NOT EXISTS (
              SELECT 1 FROM payments p WHERE p.checkout_intent_id = ci.id
          )
        ORDER BY ci.created_at DESC
        """,
        (user_id,),
    )
    payment_data = [dict(row) for row in rows]
    attempt_data = [dict(row) for row in attempts]
    return jsonify({
        'success': True,
        'data': payment_data,
        'attempts': attempt_data,
        'count': len(payment_data) + len(attempt_data),
    })


@app.route('/api/internal/checkout-intents/expire-stale', methods=['POST'])
def expire_stale_checkout_intents_internal():
    """Expire abandoned pending checkout intents (internal maintenance token required)."""
    from common.payment_fulfillment import expire_stale_checkout_intents

    expected = (optional_env("CHECKOUT_MAINTENANCE_TOKEN", "") or "").strip()
    if not expected or request.headers.get("X-Internal-Token") != expected:
        return jsonify({"success": False, "message": "Forbidden"}), 403
    limit = request.args.get("limit", 500, type=int)
    limit = max(1, min(limit, 5000))
    expired_count = expire_stale_checkout_intents(limit=limit)
    return jsonify({"success": True, "expired_count": expired_count})


@app.route('/api/checkout', methods=['POST', 'OPTIONS'])
@verify_auth_token
def create_checkout():
    return create_checkout_handler()


@app.route('/api/checkout/<intent_id>/status', methods=['GET'])
@verify_auth_token
def checkout_status(intent_id):
    return checkout_status_handler(intent_id)


@app.route('/api/webhooks/dodo', methods=['POST', 'OPTIONS'])
def dodo_webhook():
    return dodo_webhook_handler()


def _legacy_checkout_redirect():
    """Backward-compatible alias for old create-payment calls."""
    return create_checkout_handler()


@app.route('/api/create-payment', methods=['POST', 'OPTIONS'])
@verify_auth_token
def create_payment():
    return _legacy_checkout_redirect()


@app.route('/api/check-payment-status', methods=['GET'])
@verify_auth_token
def check_payment_status():
    transaction_id = request.args.get('transaction_id')
    row = query_one(
        'SELECT * FROM payments WHERE user_id=%s AND transaction_id=%s ORDER BY paid_at DESC LIMIT 1',
        (request.user['id'], transaction_id),
    )
    if not row:
        return jsonify({'success': False, 'status': 'not_found'}), 404
    return jsonify({'success': True, 'status': row['payment_status'], 'data': dict(row)})


@app.route('/api/interviews/<interview_id>', methods=['GET'])
@verify_auth_token
def get_interview(interview_id):
    row = query_one('SELECT * FROM interviews WHERE id=%s AND user_id=%s', (interview_id, request.user['id']))
    if not row:
        return jsonify({'success': False, 'message': 'Interview not found'}), 404
    return jsonify({'success': True, 'data': dict(row)})


@app.route('/api/interviews/<interview_id>', methods=['DELETE', 'OPTIONS'])
@verify_auth_token
def delete_interview(interview_id):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    execute('DELETE FROM interviews WHERE id=%s AND user_id=%s', (interview_id, request.user['id']))
    return jsonify({'success': True})


@app.route('/api/support-bot-data', methods=['GET'])
@verify_auth_token
def support_bot_data():
    user_id = request.user['id']
    user = query_one('SELECT id, email, full_name, plan, created_at FROM users WHERE id=%s', (user_id,))
    payments = query_all('SELECT * FROM payments WHERE user_id=%s ORDER BY paid_at DESC LIMIT 10', (user_id,))
    interviews = query_all(
        """
        SELECT i.*, jd.title AS job_title, i.scheduled_at AS created_at
        FROM interviews i
        LEFT JOIN job_descriptions jd ON jd.id = i.jd_id
        WHERE i.user_id=%s
        ORDER BY i.scheduled_at DESC
        LIMIT 10
        """,
        (user_id,),
    )
    resumes = query_all('SELECT * FROM resumes WHERE user_id=%s ORDER BY uploaded_at DESC LIMIT 10', (user_id,))
    jds = query_all('SELECT * FROM job_descriptions WHERE user_id=%s ORDER BY created_at DESC LIMIT 10', (user_id,))
    feedback = query_all(
        """
        SELECT f.*
        FROM interview_feedback f
        JOIN interviews i ON i.id = f.interview_id
        WHERE i.user_id=%s
        ORDER BY f.created_at DESC
        LIMIT 10
        """,
        (user_id,),
    )
    return jsonify({'success': True, 'data': {
        'user_info': dict(user) if user else {},
        'payments': [dict(row) for row in payments],
        'interviews': [dict(row) for row in interviews],
        'resumes': [dict(row) for row in resumes],
        'job_descriptions': [dict(row) for row in jds],
        'interview_feedback': [dict(row) for row in feedback],
    }})


@app.route('/functions/v1/upload-file', methods=['POST', 'OPTIONS'])
@app.route('/api/functions/v1/upload-file', methods=['POST', 'OPTIONS'])
@verify_auth_token
def legacy_upload_file():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    file = request.files['file']
    folder = validated_legacy_upload_folder(request.user['id'], request.form.get('folder'))
    if not folder:
        return jsonify({'success': False, 'error': 'Invalid upload folder'}), 400
    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400
    try:
        result = save_bytes(file.read(), folder, filename)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    return jsonify({'success': True, 'data': result})


@app.route('/functions/v1/resumes', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/api/functions/v1/resumes', methods=['GET', 'POST', 'OPTIONS'])
@verify_auth_token
def legacy_resumes():
    return resumes_api()


@app.route('/functions/v1/job-descriptions', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/api/functions/v1/job-descriptions', methods=['GET', 'POST', 'OPTIONS'])
@verify_auth_token
def legacy_job_descriptions():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    if request.method == 'GET':
        return get_job_descriptions()
    data = request.get_json() or {}
    jd = execute(
        'INSERT INTO job_descriptions (user_id, title, description, file_url, technical) VALUES (%s, %s, %s, %s, %s) RETURNING *',
        (request.user['id'], data.get('title'), data.get('description'), data.get('file_url'), data.get('technical', True)),
    )
    return jsonify({'success': True, 'data': dict(jd)}), 201


@app.route('/functions/v1/interviews', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/api/functions/v1/interviews', methods=['GET', 'POST', 'OPTIONS'])
@verify_auth_token
def legacy_interviews():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    if request.method == 'GET':
        resume_id = request.args.get('resume_id')
        jd_id = request.args.get('jd_id')
        question_set = request.args.get('question_set')
        sql = 'SELECT * FROM interviews WHERE user_id=%s'
        params = [request.user['id']]
        if resume_id:
            sql += ' AND resume_id=%s'
            params.append(resume_id)
        if jd_id:
            sql += ' AND jd_id=%s'
            params.append(jd_id)
        if question_set:
            sql += ' AND question_set=%s'
            params.append(int(question_set))
        sql += ' ORDER BY scheduled_at DESC'
        rows = query_all(sql, tuple(params))
        return jsonify({'success': True, 'data': [dict(row) for row in rows]})
    return create_interview()


@app.route('/functions/v1/interviews/<interview_id>', methods=['GET', 'PUT', 'DELETE', 'OPTIONS'])
@app.route('/api/functions/v1/interviews/<interview_id>', methods=['GET', 'PUT', 'DELETE', 'OPTIONS'])
@verify_auth_token
def legacy_interview_detail(interview_id):
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    if request.method == 'GET':
        return get_interview(interview_id)
    if request.method == 'DELETE':
        return delete_interview(interview_id)
    return update_interview(interview_id)


@app.route('/functions/v1/questions', methods=['GET', 'POST', 'OPTIONS'])
@app.route('/api/functions/v1/questions', methods=['GET', 'POST', 'OPTIONS'])
@verify_auth_token
def legacy_questions():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    if request.method == 'GET':
        resume_id = request.args.get('resume_id')
        jd_id = request.args.get('jd_id')
        question_set = request.args.get('question_set')
        sql = 'SELECT * FROM questions WHERE 1=1'
        params = []
        if resume_id:
            sql += ' AND resume_id=%s'
            params.append(resume_id)
        if jd_id:
            sql += ' AND jd_id=%s'
            params.append(jd_id)
        if question_set:
            sql += ' AND question_set=%s'
            params.append(int(question_set))
        sql += f' ORDER BY question_set DESC, {QUESTION_ORDER_SQL}'
        rows = [_serialize_question(row) for row in query_all(sql, tuple(params))]
        rows.sort(key=_question_sort_key)
        return jsonify({'success': True, 'data': rows})
    data = request.get_json() or {}
    resume_id = data.get('resume_id')
    jd_id = data.get('jd_id')
    question_set = data.get('question_set', 1)
    saved = []
    for question in data.get('questions', []):
        exp = normalize_difficulty_experience(question.get("difficulty_experience"))
        level = normalize_question_difficulty(question.get('difficulty_category') or question.get('difficulty_level'))
        row = execute(
            """
            INSERT INTO questions (interview_id, resume_id, jd_id, question_text, expected_answer, difficulty_level, difficulty_experience, question_set, requires_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                question.get('interview_id') or data.get('interview_id'),
                resume_id,
                jd_id,
                question.get('question_text') or question.get('question'),
                question.get('expected_answer') or question.get('answer'),
                level,
                exp,
                question.get('question_set') or question_set,
                question.get('requires_code', False),
            ),
        )
        saved.append(_serialize_question(row))
    return jsonify({'success': True, 'data': saved}), 201


@app.route('/functions/v1/dashboard', methods=['GET'])
@app.route('/api/functions/v1/dashboard', methods=['GET'])
@verify_auth_token
def legacy_dashboard():
    return jsonify({'success': True, 'data': _build_dashboard_pairings(request.user['id'])})


@app.route('/functions/v1/payments', methods=['GET'])
@app.route('/api/functions/v1/payments', methods=['GET'])
@verify_auth_token
def legacy_payments():
    return get_payments()


@app.route('/functions/v1/create-payment', methods=['POST', 'OPTIONS'])
@app.route('/api/functions/v1/create-payment', methods=['POST', 'OPTIONS'])
@verify_auth_token
def legacy_create_payment():
    return _legacy_checkout_redirect()


@app.route('/functions/v1/interview-feedback', methods=['GET'])
@app.route('/api/functions/v1/interview-feedback', methods=['GET'])
@verify_auth_token
def legacy_interview_feedback():
    interview_id = request.args.get('interview_id')
    if interview_id:
        row = query_one(
            """
            SELECT f.*, i.active_seconds, i.ended_at
            FROM interview_feedback f
            JOIN interviews i ON i.id = f.interview_id
            WHERE f.interview_id=%s AND i.user_id=%s
            """,
            (interview_id, request.user['id']),
        )
        if not row:
            return jsonify({'success': True, 'data': []})
        return jsonify({'success': True, 'data': [normalize_feedback_row(row)]})
    limit = int(request.args.get('limit', 100))
    rows = query_all(
        """
        SELECT f.*, i.active_seconds, i.ended_at
        FROM interview_feedback f
        JOIN interviews i ON i.id = f.interview_id
        WHERE i.user_id=%s
        ORDER BY f.created_at ASC
        LIMIT %s
        """,
        (request.user['id'], limit),
    )
    return jsonify({'success': True, 'data': [normalize_feedback_row(row) for row in rows]})


@app.route('/functions/v1/transcripts', methods=['GET'])
@app.route('/api/functions/v1/transcripts', methods=['GET'])
@verify_auth_token
def legacy_transcripts():
    interview_id = request.args.get('interview_id')
    row = query_one('SELECT * FROM transcripts WHERE interview_id=%s', (interview_id,))
    return jsonify({'success': True, 'data': [dict(row)] if row else []})


@app.route('/functions/v1/chat-history', methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
@app.route('/api/functions/v1/chat-history', methods=['GET', 'POST', 'DELETE', 'OPTIONS'])
@verify_auth_token
def legacy_chat_history():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    interview_id = request.args.get('interview_id') or (request.get_json(silent=True) or {}).get('interview_id')
    if not interview_id:
        return jsonify({'success': False, 'error': 'interview_id required'}), 400
    if request.method == 'GET':
        rows = query_all('SELECT * FROM chat_history WHERE interview_id=%s ORDER BY created_at ASC', (interview_id,))
        content = '\n'.join(f"{row['role']}:{row['content']}" for row in rows)
        ui_state = _interview_session_ui_state(interview_id, request.user['id'])
        return jsonify({
            'success': True,
            'history': [{'content': content}] if content else [],
            **ui_state,
        })
    if request.method == 'DELETE':
        execute('DELETE FROM chat_history WHERE interview_id=%s', (interview_id,))
        return jsonify({'success': True})
    data = request.get_json() or {}
    content = data.get('content', '')
    if '\n' in content:
        execute('DELETE FROM chat_history WHERE interview_id=%s', (interview_id,))
        lines = [line for line in content.splitlines() if line.strip()]
    else:
        lines = [content] if content else []
    for line in lines:
        role = 'assistant'
        message = line
        if ':' in line:
            speaker, message = line.split(':', 1)
            role = 'assistant' if speaker.strip().lower() in {'assistant', 'interviewer'} else 'user'
        execute('INSERT INTO chat_history (interview_id, role, content) VALUES (%s, %s, %s)', (interview_id, role, message.strip()))
    return jsonify({'success': True})


@app.route('/functions/v1/support-bot-data', methods=['GET'])
@app.route('/api/functions/v1/support-bot-data', methods=['GET'])
@verify_auth_token
def legacy_support_bot_data():
    return support_bot_data()

# ─────────────────────────────────────────────────────────────────────────────
#  STARTUP
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
#  TOKEN REFRESH
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/refresh-token', methods=['POST', 'OPTIONS'])
@verify_auth_token_allow_expired
def refresh_token():
    """Issue a fresh JWT for an already-authenticated user."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    user = query_one(
        'SELECT {columns} FROM users WHERE id=%s'.format(columns=build_user_columns(_USER_PUBLIC_FIELDS)),
        (request.user['id'],)
    )
    if not user:
        return jsonify({'error': 'User not found'}), 404
    token = create_token(str(user['id']), user['email'], user['full_name'], user['plan'])
    return _issue_auth_response({"user": serialize_user(user)}, token)


@app.route('/api/logout', methods=['POST', 'OPTIONS'])
def logout():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    resp = make_response(jsonify({'message': 'Logged out'}), 200)
    clear_auth_cookie(resp)
    return resp


# ─────────────────────────────────────────────────────────────────────────────
#  PASSWORD RESET
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/forgot-password', methods=['POST', 'OPTIONS'])
@rate_limit(max_calls=3, window_seconds=300)
def forgot_password():
    """Request a password-reset link. Always returns 200 to prevent email enumeration."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({'message': 'If an account exists, a reset link has been sent.'}), 200
    user = query_one(
        'SELECT id, email, username, full_name FROM users WHERE lower(email)=%s', (email,)
    )
    if not user:
        return jsonify({'message': 'If an account exists, a reset link has been sent.'}), 200
    try:
        ensure_password_reset_schema()
        # Invalidate old tokens
        execute(
            'UPDATE password_reset_tokens SET consumed_at=now() WHERE user_id=%s AND consumed_at IS NULL',
            (user['id'],)
        )
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        execute(
            "INSERT INTO password_reset_tokens (id, user_id, token_hash, expires_at) VALUES (%s,%s,%s, now() + interval '1 hour')",
            (str(uuid.uuid4()), user['id'], token_hash)
        )
        reset_link = build_public_url('reset-password', token=token)
        text_body = (
            f"Hi {user.get('full_name') or user.get('username') or 'there'},\n\n"
            f"Reset your InterviewCoach password by opening this link:\n{reset_link}\n\n"
            f"This link expires in 1 hour. If you did not request this, ignore this email."
        )
        html_body = (
            f"<p>Hi {user.get('full_name') or user.get('username') or 'there'},</p>"
            f"<p>Reset your InterviewCoach password by clicking below:</p>"
            f"<p><a href=\"{reset_link}\">{reset_link}</a></p>"
            f"<p>This link expires in 1 hour.</p>"
        )
        if smtp_is_configured():
            send_email('Reset your InterviewCoach password', user['email'], text_body, html_body)
            return jsonify({
                'message': 'If an account exists, a reset link has been sent.',
                'delivery': 'email',
            }), 200
        if _allow_manual_auth_links():
            print(f"[WARN] SMTP not configured. Reset link for {user['email']}: {reset_link}")
            return jsonify({
                'message': 'SMTP is not configured, so use the reset link shown below.',
                'delivery': 'manual',
                'reset_link': reset_link,
            }), 200
        return jsonify({
            'message': 'If an account exists, a reset link has been sent.',
            'delivery': 'email',
        }), 200
    except Exception as e:
        print(f"[ERROR] forgot_password: {e}")
    return jsonify({'message': 'If an account exists, a reset link has been sent.'}), 200


@app.route('/api/forgot-username', methods=['POST', 'OPTIONS'])
@rate_limit(max_calls=3, window_seconds=300)
def forgot_username():
    """Send or return a username reminder for an email address."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    generic_message = 'If an account exists, the username reminder has been sent.'
    if not email:
        return jsonify({'message': generic_message}), 200
    user = query_one(
        'SELECT id, email, username, full_name FROM users WHERE lower(email)=%s', (email,)
    )
    if not user:
        return jsonify({'message': generic_message}), 200
    try:
        text_body = (
            f"Hi {user.get('full_name') or 'there'},\n\n"
            f"Your InterviewCoach username is: {user['username']}\n\n"
            f"You can now sign in using either your email or username."
        )
        html_body = (
            f"<p>Hi {user.get('full_name') or 'there'},</p>"
            f"<p>Your InterviewCoach username is: <strong>{user['username']}</strong></p>"
            f"<p>You can now sign in using either your email or username.</p>"
        )
        if smtp_is_configured():
            send_email('Your InterviewCoach username', user['email'], text_body, html_body)
            return jsonify({'message': generic_message, 'delivery': 'email'}), 200

        print(f"[WARN] SMTP not configured. Username reminder for {user['email']}: {user['username']}")
        return jsonify({
            'message': generic_message,
            'delivery': 'manual',
            'username': user['username'],
        }), 200
    except Exception as e:
        print(f"[ERROR] forgot_username: {e}")
        return jsonify({'message': generic_message}), 200


@app.route('/api/reset-password', methods=['POST', 'OPTIONS'])
@rate_limit(max_calls=5, window_seconds=300)
def reset_password():
    """Consume a reset token and set a new password."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    data = request.get_json() or {}
    token = data.get('token', '').strip()
    new_password = data.get('password', '')
    if not token or not new_password:
        return jsonify({'error': 'Token and new password are required'}), 400
    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    record = query_one(
        """
        SELECT prt.user_id, u.email, u.full_name, u.username, u.plan
        FROM password_reset_tokens prt
        JOIN users u ON u.id = prt.user_id
        WHERE prt.token_hash=%s AND prt.consumed_at IS NULL AND prt.expires_at > now()
        """,
        (token_hash,)
    )
    if not record:
        return jsonify({'error': 'Reset link is invalid or has expired'}), 400
    execute(
        'UPDATE password_reset_tokens SET consumed_at=now() WHERE token_hash=%s', (token_hash,)
    )
    execute(
        'UPDATE users SET password_hash=%s WHERE id=%s',
        (hash_password(new_password), record['user_id'])
    )
    new_token = create_token(str(record['user_id']), record['email'], record['full_name'], record['plan'])
    return _issue_auth_response({'message': 'Password updated successfully.'}, new_token)


# ─────────────────────────────────────────────────────────────────────────────
#  ACCOUNT DELETION (GDPR)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/me', methods=['DELETE', 'OPTIONS'])
@verify_auth_token
def delete_account():
    """Permanently delete the authenticated user and all their data."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    data = request.get_json() or {}
    password = data.get('password', '')
    user_id = request.user['id']
    user = query_one('SELECT password_hash FROM users WHERE id=%s', (user_id,))
    if not user or not check_password(password, user['password_hash']):
        return jsonify({'error': 'Password confirmation failed'}), 403
    try:
        # Delete stored audio/resume files
        audio_folder = build_protected_storage_path("audio", user_id)
        audio_files = list_folder(audio_folder) if audio_folder else []
        if audio_files:
            delete_files([f['relative_path'] for f in audio_files])
        resume_rows = query_all('SELECT stored_path FROM resumes WHERE user_id=%s', (user_id,))
        if resume_rows:
            delete_files([r['stored_path'] for r in resume_rows if r.get('stored_path')])
        # Cascade deletes handle all related DB rows
        execute('DELETE FROM users WHERE id=%s', (user_id,))
        return jsonify({'success': True, 'message': 'Account deleted.'})
    except Exception as e:
        print(f'[ERROR] delete_account: {e}')
        return jsonify({'error': 'Account deletion failed'}), 500


# ─────────────────────────────────────────────────────────────────────────────
#  INTERVIEW HISTORY  (paginated)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/interview-history', methods=['GET'])
@verify_auth_token
def interview_history():
    """Paginated list of the user's past interviews with feedback summaries."""
    user_id = request.user['id']
    page  = max(1, int(request.args.get('page', 1)))
    limit = min(50, max(1, int(request.args.get('limit', 10))))
    offset = (page - 1) * limit

    total_row = query_one(
        "SELECT COUNT(*) AS cnt FROM interviews WHERE user_id=%s AND status IN ('ENDED', 'completed')",
        (user_id,),
    )
    total = int(total_row['cnt']) if total_row else 0

    rows = query_all(
        """
        SELECT i.id, i.status, i.scheduled_at, i.attempt_number,
               jd.title as job_title,
               f.summary, f.metrics, f.audio_url
        FROM interviews i
        LEFT JOIN job_descriptions jd ON jd.id = i.jd_id
        LEFT JOIN interview_feedback f ON f.interview_id = i.id
        WHERE i.user_id=%s AND i.status IN ('ENDED', 'completed')
        ORDER BY i.scheduled_at DESC
        LIMIT %s OFFSET %s
        """,
        (user_id, limit, offset)
    )
    return jsonify({
        'success': True,
        'data': [dict(r) for r in rows],
        'page': page,
        'limit': limit,
        'total': total,
        'total_pages': max(1, -(-total // limit))
    })


# ─────────────────────────────────────────────────────────────────────────────
#  SESSION CLEANUP  (admin utility)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/admin/purge-sessions', methods=['POST'])
@verify_auth_token
def admin_purge_sessions():
    """Purge stale interview sessions older than N hours (admin only)."""
    if not _is_admin_user(request.user):
        return jsonify({'error': 'Forbidden'}), 403
    hours = int((request.get_json() or {}).get('hours', 24))
    purge_old_sessions(hours)
    return jsonify({'success': True, 'message': f'Sessions older than {hours}h purged.'})

import atexit
from common.db import close_pool

atexit.register(close_pool)

if optional_env("ENABLE_AI_WARMUP", "false").lower() not in {"0", "false", "no"}:
    print("[INFO] Scheduling AI warmup...")
    schedule_background_ai_warmup()
else:
    print("[INFO] AI warmup disabled — Whisper/head tracking load on first use (lower idle RAM)")
print("[INFO] Backend ready")

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
