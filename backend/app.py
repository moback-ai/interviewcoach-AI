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
import threading
import re
import ipaddress
from urllib.parse import urlencode

import soundfile as sf
import cv2
import numpy as np
try:
    import mediapipe as mp
except Exception as mediapipe_import_error:
    mp = None
    print(f"[WARN] MediaPipe import failed: {mediapipe_import_error}")

from flask import Flask, request, jsonify, send_from_directory, abort, render_template_string
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from PIL import Image, UnidentifiedImageError
from datetime import datetime
from werkzeug.utils import secure_filename
from pydub import AudioSegment
import requests as http_requests

# ── Environment ───────────────────────────────────────────────────────────────
from common.runtime_config import load_runtime_config, optional_env, require_env

load_runtime_config()

INTERVIEW_PATH = os.path.join(os.path.dirname(__file__), "INTERVIEW")
if INTERVIEW_PATH not in sys.path:
    sys.path.append(INTERVIEW_PATH)

SUPPORT_BOT_PATH = os.path.join(os.path.dirname(__file__), "Support-bot")
if SUPPORT_BOT_PATH not in sys.path:
    sys.path.append(SUPPORT_BOT_PATH)

# ── Internal modules ──────────────────────────────────────────────────────────
from common.GPU_Check import get_device
from common.auth import verify_auth_token, create_token, hash_password, check_password
from common.db import query_one, query_all, execute
from common.email_utils import send_email, smtp_is_configured
from common.storage import save_bytes, save_from_path, read_bytes, list_folder, delete_files, public_url
from common.rate_limit import rate_limit, user_rate_limit
from common.session_store import load_session, save_session, delete_session, purge_old_sessions

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

device = get_device()

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = int(optional_env("MAX_CONTENT_MB", "200")) * 1024 * 1024

DOMAIN = require_env("DOMAIN")
EMAIL_VERIFICATION_TTL_HOURS = int(optional_env("EMAIL_VERIFICATION_TTL_HOURS", "24"))

CORS(app,
     supports_credentials=True,
     origins=[DOMAIN, "http://localhost:5173", "http://127.0.0.1:5173"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept"])

_ALLOWED_ORIGINS = [DOMAIN, "http://localhost:5173", "http://127.0.0.1:5173"]
socketio = SocketIO(app, cors_allowed_origins=_ALLOWED_ORIGINS, async_mode="threading")


def get_public_origin():
    return require_env("DOMAIN").rstrip("/")


def build_public_url(path: str, **params):
    base = f"{get_public_origin()}/{path.lstrip('/')}"
    if not params:
        return base
    return f"{base}?{urlencode(params)}"


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
    if normalized in {"weak", "junior", "novice"}:
        return "beginner"
    if normalized in {"medium", "mid", "strong_mid"}:
        return "intermediate"
    if normalized in {"strong", "expert", "senior", "advanced"}:
        return "expert"
    return "beginner"


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


def ensure_questions_schema():
    execute(
        """
        ALTER TABLE questions
        ADD COLUMN IF NOT EXISTS difficulty_experience TEXT NOT NULL DEFAULT 'beginner'
        """
    )


def serialize_user(user):
    if not user:
        return None
    payload = dict(user)
    payload["id"] = str(payload["id"])
    payload["email_verified"] = bool(payload.get("email_verified_at"))
    payload.setdefault("user_metadata", {})
    payload["user_metadata"]["full_name"] = payload.get("full_name", "")
    return payload


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

    if allow_manual_fallback:
        print(f"[WARN] SMTP not configured. Verification link for {user['email']}: {verification_link}")
        return build_verification_payload(user, verification_link, delivery="manual")

    raise RuntimeError("SMTP is not configured for verification emails.")


def get_user_for_auth(identifier: str):
    normalized = (identifier or "").strip().lower()
    return query_one(
        """
        SELECT id, email, username, password_hash, full_name, plan, created_at, email_verified_at
        FROM users
        WHERE lower(email) = %s OR lower(coalesce(username, '')) = %s
        """,
        (normalized, normalized),
    )


ensure_auth_schema()
ensure_questions_schema()

PUBLIC_DOC_ENDPOINTS = {
    "/api/health",
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
    return jsonify(build_openapi_spec())


@app.route('/api/docs', methods=['GET'])
def swagger_ui():
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


DEFAULT_ADMIN_LOG_EMAILS = {
    "govardhanr@moback.com",
}
DEFAULT_ADMIN_LOG_USERNAMES = {
    "govardhan",
}


def _split_env_values(value: str):
    return {item.strip().lower() for item in (value or "").split(",") if item.strip()}


def _extract_request_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip
    return (request.headers.get("X-Real-IP") or request.remote_addr or "").strip()


def _ip_allowlist_entries():
    raw = optional_env("ADMIN_LOG_IP_ALLOWLIST")
    if not raw:
        return []
    entries = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            entries.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            pass
    return entries


def _is_allowed_ip(ip_text: str):
    allowlist = _ip_allowlist_entries()
    if not allowlist:
        return True
    try:
        ip_obj = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    return any(ip_obj in network for network in allowlist)


def _get_admin_user_record(user_id):
    return query_one(
        "SELECT id, username, email, full_name, plan FROM users WHERE id=%s",
        (user_id,),
    )


def _can_view_admin_logs(user):
    if not user:
        return False
    user_email = (user.get("email") or "").strip().lower()
    user_plan = (user.get("plan") or "").strip().lower()
    user_record = _get_admin_user_record(user.get("id"))
    username = ((user_record or {}).get("username") or "").strip().lower()

    allowed_emails = _split_env_values(optional_env("ADMIN_LOG_VIEWER_EMAILS")) or DEFAULT_ADMIN_LOG_EMAILS
    allowed_usernames = _split_env_values(optional_env("ADMIN_LOG_VIEWER_USERNAMES")) or DEFAULT_ADMIN_LOG_USERNAMES

    return (
        user_plan == "admin"
        or user_email in allowed_emails
        or username in allowed_usernames
    )


def _redact_log_text(text: str):
    redacted = text
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9\-_\.]+", "Bearer [REDACTED]", redacted)
    redacted = re.sub(r'("?(?:password|token|secret|authorization|api[_-]?key)"?\s*[:=]\s*)"[^"]+"', r'\1"[REDACTED]"', redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", r"\1***@\2", redacted)
    return redacted


def _tail_text_file(path: str, line_count: int = 200):
    if not os.path.exists(path):
        return {"available": False, "path": path, "lines": []}
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()[-line_count:]
    return {
        "available": True,
        "path": path,
        "lines": [_redact_log_text(line.rstrip("\n")) for line in lines],
    }


def _database_log_snapshot():
    summary = {
        "connections": query_all(
            """
            SELECT state, count(*) AS total
            FROM pg_stat_activity
            WHERE datname = current_database()
            GROUP BY state
            ORDER BY state NULLS LAST
            """
        ),
        "table_counts": {
            "users": (query_one("SELECT count(*) AS total FROM users") or {}).get("total", 0),
            "interviews": (query_one("SELECT count(*) AS total FROM interviews") or {}).get("total", 0),
            "payments": (query_one("SELECT count(*) AS total FROM payments") or {}).get("total", 0),
            "questions": (query_one("SELECT count(*) AS total FROM questions") or {}).get("total", 0),
        },
    }
    lines = [
        f"users={summary['table_counts']['users']}",
        f"interviews={summary['table_counts']['interviews']}",
        f"payments={summary['table_counts']['payments']}",
        f"questions={summary['table_counts']['questions']}",
    ]
    for row in summary["connections"]:
        lines.append(f"connections[{row.get('state') or 'unknown'}]={row.get('total')}")
    return {
        "available": True,
        "path": "database diagnostics",
        "lines": lines,
        "summary": summary,
    }


@app.route('/api/admin/logs', methods=['GET'])
@verify_auth_token
def admin_logs():
    client_ip = _extract_request_ip()
    if not _is_allowed_ip(client_ip):
        return jsonify({"error": "IP not allowed for admin logs", "client_ip": client_ip}), 403
    if not _can_view_admin_logs(request.user):
        return jsonify({"error": "Admin access required"}), 403

    source = (request.args.get("source") or "backend-error").strip().lower()
    line_count = min(max(int(request.args.get("lines", 200)), 20), 500)

    sources = {
        "backend-error": lambda: _tail_text_file("/home/ubuntu/.pm2/logs/backend-error.log", line_count),
        "backend-out": lambda: _tail_text_file("/home/ubuntu/.pm2/logs/backend-out.log", line_count),
        "database": _database_log_snapshot,
    }

    resolver = sources.get(source)
    if not resolver:
        return jsonify({
            "error": "Unknown log source",
            "available_sources": sorted(sources.keys()),
        }), 400

    payload = resolver()
    payload.update({
        "source": source,
        "requested_by": request.user.get("email"),
        "client_ip": client_ip,
    })
    return jsonify({"success": True, "data": payload})

# ─────────────────────────────────────────────────────────────────────────────
#  HEAD TRACKING
# ─────────────────────────────────────────────────────────────────────────────

class EyeContactDetector_Callib:
    def __init__(self):
        if mp is None:
            raise RuntimeError("mediapipe is not installed")
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
        self.min_frame_interval = 0.1
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True, max_num_faces=1,
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


def get_head_tracking_detector():
    global detector
    if detector is not None:
        return detector
    with detector_lock:
        if detector is not None:
            return detector
        try:
            detector = EyeContactDetector_Callib()
            print("[INFO] Head tracking initialized")
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
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"decode_image error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  WHISPER (speech-to-text)
# ─────────────────────────────────────────────────────────────────────────────

from faster_whisper import WhisperModel

whisper_model = None

def initialize_whisper():
    global whisper_model
    if whisper_model is not None:
        return
    model_size = optional_env("WHISPER_MODEL", "base")
    whisper_device = "cpu" if device == "mps" else device
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
    except subprocess.CalledProcessError:
        return None

def is_blank_audio(audio_path, rms_threshold=0.005):
    try:
        audio, _ = sf.read(audio_path)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return np.sqrt(np.mean(audio**2)) < rms_threshold
    except Exception:
        return False

def _transcribe(wav_path):
    segs, info = whisper_model.transcribe(wav_path, beam_size=5, language="en", task="transcribe")
    return " ".join(s.text for s in list(segs))

def process_audio_file(file):
    global whisper_model
    if whisper_model is None:
        initialize_whisper()
    if whisper_model is None:
        return {"success": False, "error": "Speech model unavailable"}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tf:
        original = tf.name
        file.save(original)

    wav_path = None
    try:
        wav_path = convert_to_wav(original)
        if not wav_path:
            return {"success": False, "error": "Audio conversion failed"}
        if is_blank_audio(wav_path):
            return {"success": True, "transcription": ""}

        for attempt in range(3):
            try:
                text = _transcribe(wav_path)
                text = text.strip()
                # Basic corruption check
                clean = text.replace("!", "").replace(" ", "")
                if not clean:
                    if attempt < 2 and reinitialize_whisper():
                        continue
                    return {"success": True, "transcription": ""}
                return {"success": True, "transcription": text}
            except Exception as e:
                print(f"[WARN] Transcription attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    reinitialize_whisper()
        return {"success": False, "error": "Transcription failed after retries"}
    finally:
        for p in [original, wav_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


def schedule_background_ai_warmup():
    if optional_env("ENABLE_AI_WARMUP", "true").lower() in {"0", "false", "no"}:
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

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "version": "2.0.0"})


def extract_text_from_uploaded_document(file_path, ext):
    ext = ext.lower()
    if ext == 'txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as handle:
            return handle.read()
    if ext == 'pdf':
        import PyPDF2
        text = []
        with open(file_path, 'rb') as handle:
            reader = PyPDF2.PdfReader(handle)
            for page in reader.pages:
                text.append(page.extract_text() or "")
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


def summarize_job_description_text(raw_text):
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    text = "\n".join(lines).strip()
    if not text:
        return {"job_title": "", "job_description": ""}

    title = ""
    for line in lines[:12]:
        normalized = line.lower()
        if 2 <= len(line) <= 120 and any(keyword in normalized for keyword in [
            'engineer', 'developer', 'manager', 'analyst', 'consultant', 'specialist',
            'architect', 'lead', 'qa', 'tester', 'intern', 'administrator', 'devops',
            'sre', 'support', 'designer', 'scientist'
        ]):
            title = line
            break

    if not title:
        title = lines[0][:120]

    compact_description = " ".join(segment.strip() for segment in lines[:40])
    compact_description = compact_description[:4000].strip()

    return {
        "job_title": title,
        "job_description": compact_description,
    }


def classify_job_description_is_technical(job_title, job_description):
    haystack = f"{job_title} {job_description}".lower()
    technical_keywords = [
        'python', 'java', 'javascript', 'typescript', 'sql', 'api', 'backend', 'frontend',
        'full stack', 'fullstack', 'developer', 'engineer', 'devops', 'sre', 'automation',
        'selenium', 'aws', 'cloud', 'kubernetes', 'docker', 'microservices', 'react',
        'node', 'coding', 'programming', 'software', 'data engineer', 'machine learning',
        'qa automation', 'test automation', 'ci/cd'
    ]
    non_technical_keywords = [
        'sales', 'marketing', 'hr', 'human resources', 'recruiter', 'customer support',
        'business development', 'operations manager', 'office assistant'
    ]
    if any(keyword in haystack for keyword in technical_keywords):
        return True
    if any(keyword in haystack for keyword in non_technical_keywords):
        return False
    return False


def infer_candidate_name_from_text(raw_text):
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for line in lines[:5]:
        words = line.split()
        if 1 <= len(words) <= 4 and sum(1 for word in words if word[:1].isupper()) >= max(1, len(words) - 1):
            return line[:80]
    return "Candidate"


def extract_keywords_for_questions(resume_text, job_description):
    combined = f"{resume_text}\n{job_description}".lower()
    keyword_order = [
        "python", "flask", "django", "fastapi", "javascript", "typescript", "react",
        "node", "sql", "postgresql", "mysql", "mongodb", "aws", "docker", "kubernetes",
        "ci/cd", "linux", "rest api", "microservices", "testing", "automation", "devops",
        "selenium", "git", "redis", "system design", "machine learning"
    ]
    found = []
    for keyword in keyword_order:
        if keyword in combined and keyword not in found:
            found.append(keyword)
    return found[:8]


def build_local_question_set(job_title, job_description, resume_text, question_counts):
    candidate_name = infer_candidate_name_from_text(resume_text)
    keywords = extract_keywords_for_questions(resume_text, job_description)
    primary_skill = keywords[0] if keywords else "the core skills in your background"
    secondary_skill = keywords[1] if len(keywords) > 1 else primary_skill

    templates = {
        "beginner": [
            (
                f"Can you introduce yourself and explain how your experience prepares you for the {job_title} role?",
                f"A strong answer should summarize relevant experience, highlight impact, and connect the candidate's background to the {job_title} responsibilities."
            ),
            (
                f"What hands-on experience do you have with {primary_skill}?",
                f"The answer should describe real projects, responsibilities, tools used, and measurable outcomes involving {primary_skill}."
            ),
            (
                f"Which parts of this job description feel most aligned with your recent work?",
                "A good response should map past responsibilities to the posted role and mention concrete examples."
            ),
        ],
        "medium": [
            (
                f"Tell me about a project where you used {primary_skill} to solve a meaningful problem.",
                f"A strong answer should cover the problem, approach, tradeoffs, implementation details, and results using {primary_skill}."
            ),
            (
                f"How would you improve reliability and maintainability in a system that uses {secondary_skill}?",
                f"The answer should discuss architecture, testing, observability, and operational tradeoffs related to {secondary_skill}."
            ),
            (
                f"Describe a situation where you had to balance speed of delivery with code quality or technical debt.",
                "A good answer should explain prioritization, stakeholder communication, and the long-term mitigation plan."
            ),
        ],
        "hard": [
            (
                f"Design an approach for scaling a {job_title} workload while keeping performance, security, and cost under control.",
                "A strong answer should cover architecture decisions, scaling strategy, observability, failure handling, and tradeoffs."
            ),
            (
                f"What is the most complex technical decision you have made involving {primary_skill}, and how did you evaluate alternatives?",
                f"The answer should explain constraints, alternatives considered, tradeoffs, risks, and the final outcome around {primary_skill}."
            ),
            (
                "If production started failing intermittently right after a release, how would you investigate and stabilize it?",
                "A good response should include triage steps, rollback or mitigation, logs/metrics, communication, and prevention."
            ),
        ],
        "coding": [
            (
                f"Write or outline a solution for a practical {primary_skill} problem relevant to this role, and explain the time and space complexity.",
                f"A strong answer should include a correct approach, clean structure, edge cases, and complexity analysis using {primary_skill} concepts."
            ),
            (
                f"Implement a small utility or API handler using {secondary_skill} and explain how you would test it.",
                f"The answer should demonstrate coding structure, correctness, testability, and reasoning using {secondary_skill}."
            ),
        ],
    }

    questions = []

    def answer_variant(expected_answer, experience):
        if experience == "beginner":
            return (
                f"A concise answer should cover the main point clearly. {expected_answer} "
                "Keep the response direct and mention one relevant example if possible."
            )
        if experience == "intermediate":
            return (
                f"A stronger answer should add context, reasoning, and a concrete example. {expected_answer} "
                "Include the situation, action taken, and result or tradeoff."
            )
        return (
            f"An expert answer should connect the example to business impact, alternatives, risks, and lessons learned. "
            f"{expected_answer} Explain why the approach was chosen and how success was measured."
        )

    def append_question(prompt, expected_answer, difficulty, requires_code=False):
        normalized_difficulty = normalize_question_difficulty("medium" if requires_code else difficulty)
        for experience in ("beginner", "intermediate", "expert"):
            questions.append({
                "question_text": prompt,
                "expected_answer": answer_variant(expected_answer, experience),
                "difficulty_level": normalized_difficulty,
                "difficulty_category": normalized_difficulty,
                "difficulty_experience": experience,
                "requires_code": requires_code,
            })
    normalized_counts = {
        "beginner": int((question_counts or {}).get("beginner", 0) or 0),
        "medium": int((question_counts or {}).get("medium", 0) or 0),
        "hard": int((question_counts or {}).get("hard", 0) or 0),
        "coding": int((question_counts or {}).get("coding", 0) or 0),
    }

    for difficulty, count in normalized_counts.items():
        if count <= 0:
            continue
        bank = templates[difficulty]
        for index in range(count):
            prompt, expected = bank[index % len(bank)]
            append_question(prompt, expected, difficulty, difficulty == "coding")

    return {
        "success": True,
        "candidate": candidate_name,
        "questions": questions,
        "questions_count": len(questions),
    }


def ollama_ready(timeout_seconds=2):
    try:
        response = http_requests.get(
            optional_env("OLLAMA_HEALTH_URL", "http://127.0.0.1:11434/api/tags"),
            timeout=timeout_seconds,
        )
        return response.ok
    except Exception:
        return False

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
            RETURNING id, username, email, full_name, plan, created_at, email_verified_at
            """,
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
    return jsonify({
        "token": token,
        "user": serialize_user(user)
    })


@app.route('/api/check-email', methods=['POST', 'OPTIONS'])
def check_email():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    user = query_one("SELECT id FROM users WHERE email = %s", (email,))
    return jsonify({"exists": user is not None})


@app.route('/api/check-username', methods=['POST', 'OPTIONS'])
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
def resend_verification():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({"error": "Email is required"}), 400
    user = query_one(
        """
        SELECT id, username, email, full_name, plan, created_at, email_verified_at
        FROM users WHERE lower(email) = %s
        """,
        (email,),
    )
    if not user:
        return jsonify({"error": "Account not found"}), 404
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
        SELECT evt.user_id, u.email, u.username, u.full_name, u.plan, u.created_at, u.email_verified_at
        FROM email_verification_tokens evt
        JOIN users u ON u.id = evt.user_id
        WHERE evt.token_hash = %s AND evt.consumed_at IS NULL AND evt.expires_at > now()
        """,
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
        RETURNING id, username, email, full_name, plan, created_at, email_verified_at
        """,
        (record['user_id'],),
    )
    token_value = create_token(str(user['id']), user['email'], user['full_name'], user['plan'])
    return jsonify({
        "message": "Email verified successfully.",
        "token": token_value,
        "user": serialize_user(user),
    }), 200


@app.route('/api/me', methods=['GET'])
@verify_auth_token
def get_me():
    user = query_one("SELECT id, username, email, full_name, plan, created_at, email_verified_at FROM users WHERE id = %s",
                     (request.user['id'],))
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": serialize_user(user)})

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
    filename = f"{uuid.uuid4()}.{ext}"
    folder = f"resumes/{user_id}"
    result = save_bytes(file.read(), folder, filename)
    resume = execute(
        "INSERT INTO resumes (user_id, file_url, file_name, stored_path) VALUES (%s, %s, %s, %s) RETURNING id, file_url, file_name",
        (user_id, result['public_url'], file.filename, result['relative_path'])
    )
    return jsonify({"success": True, "data": {
        "resume_id": str(resume['id']),
        "url": result['public_url'],
        "path": result['relative_path'],
        "file_name": file.filename
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
    jd = execute(
        "INSERT INTO job_descriptions (user_id, title, description, technical) VALUES (%s,%s,%s,%s) RETURNING *",
        (request.user['id'], data.get('title'), data.get('description'), data.get('technical', True))
    )
    return jsonify({"success": True, "data": dict(jd)}), 201


@app.route('/api/job-descriptions', methods=['GET'])
@verify_auth_token
def get_job_descriptions():
    rows = query_all("SELECT * FROM job_descriptions WHERE user_id=%s ORDER BY created_at DESC",
                     (request.user['id'],))
    return jsonify({"success": True, "data": [dict(r) for r in rows]})

# ─────────────────────────────────────────────────────────────────────────────
#  INTERVIEWS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/interviews', methods=['POST', 'OPTIONS'])
@verify_auth_token
def create_interview():
    if request.method == 'OPTIONS':
        return jsonify({"message": "OK"}), 200
    data = request.get_json() or {}
    row = execute(
        "INSERT INTO interviews (user_id, resume_id, jd_id, question_set, retake_from, attempt_number) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
        (request.user['id'], data.get('resume_id'), data.get('jd_id'),
         data.get('question_set'), data.get('retake_from'), data.get('attempt_number', 1))
    )
    return jsonify({"success": True, "data": dict(row)}), 201


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
    execute("UPDATE interviews SET status=%s WHERE id=%s",
            (data.get('status', 'ACTIVE'), interview_id))
    return jsonify({"success": True})

# ─────────────────────────────────────────────────────────────────────────────
#  INTERVIEW DATA  (implements the app API interview-data)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/interview-data', methods=['GET'])
@verify_auth_token
def get_interview_data():
    interview_id = request.args.get('interview_id')
    interview = query_one(
        "SELECT i.*, jd.title, jd.description FROM interviews i "
        "LEFT JOIN job_descriptions jd ON jd.id = i.jd_id WHERE i.id=%s",
        (interview_id,)
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
    row = query_one("SELECT * FROM interview_feedback WHERE interview_id=%s", (interview_id,))
    if not row:
        return jsonify({"success": False, "message": "Not found"}), 404
    return jsonify({"success": True, "data": dict(row)})

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
            result = summarize_job_description_text(extract_text_from_uploaded_document(temp_path, ext))
            job_title = result.get('job_title', '')
            job_description = result.get('job_description', '')
            is_technical = classify_job_description_is_technical(job_title, job_description)
            return jsonify({"success": True, "data": {
                "job_title": job_title,
                "job_description": job_description,
                "is_technical": is_technical
            }})
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


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
    try:
        is_technical = classify_job_description_is_technical(job_title, job_description)
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
        job_description = data.get('job_description')
        job_title = data.get('job_title')
        if not all([resume_url, job_description, job_title]):
            return jsonify({"success": False, "message": "resume_url, job_description, job_title required"}), 400

        # Download resume from local storage or URL
        public_storage_url = require_env("PUBLIC_STORAGE_URL")
        if resume_url.startswith(public_storage_url):
            # Local storage file
            relative = resume_url.replace(public_storage_url, "").lstrip("/")
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
            if not resume_text or not resume_text.strip():
                return jsonify({
                    "success": False,
                    "message": "Resume is empty. Please upload a resume with readable content before generating questions."
                }), 400
            question_counts = data.get('question_counts', {'beginner': 2, 'medium': 2, 'hard': 2})
            try:
                if not ollama_ready():
                    raise RuntimeError("Ollama is unavailable")
                from INTERVIEW.Resumeparser import run_pipeline_from_api
                result = run_pipeline_from_api(
                    resume_path=temp_resume,
                    job_title=job_title,
                    job_description=job_description,
                    question_counts=question_counts,
                    include_answers=True,
                    split=data.get('split', False),
                    resume_pct=data.get('resume_pct', 50),
                    jd_pct=data.get('jd_pct', 50),
                    blend=data.get('blend', False),
                    blend_pct_resume=data.get('blend_pct_resume', 50),
                    blend_pct_jd=data.get('blend_pct_jd', 50),
                    max_retries=1,
                )
            except Exception as pipeline_error:
                print(f"[WARN] Falling back to local question generator: {pipeline_error}")
                result = build_local_question_set(job_title, job_description, resume_text, question_counts)
            if not result.get('success'):
                return jsonify({"success": False, "message": result.get('error', 'Pipeline failed')}), 500
            return jsonify({"success": True, "data": {
                "questions": result['questions'],
                "questions_count": result['questions_count'],
                "candidate_name": result['candidate']
            }})
        finally:
            if os.path.exists(temp_resume):
                os.unlink(temp_resume)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# ─────────────────────────────────────────────────────────────────────────────
#  TRANSCRIBE AUDIO
# ─────────────────────────────────────────────────────────────────────────────

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
    result = process_audio_file(file)
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

@app.route('/api/generate-response', methods=['POST'])
@verify_auth_token
@user_rate_limit(max_calls=60, window_seconds=60)
def generate_response():
    try:
        data = request.get_json() or {}
        user_input = data.get('message', '').strip()
        interview_id = data.get('interview_id')
        if not user_input:
            return jsonify({"success": False, "message": "Message required"}), 400
        if not interview_id:
            return jsonify({"success": False, "message": "interview_id required"}), 400

        auth_token = request.headers.get('Authorization', '').split(' ')[-1]

        # Fetch interview data directly (no loopback HTTP call)
        interview_row = query_one(
            "SELECT i.*, jd.title, jd.description FROM interviews i "
            "LEFT JOIN job_descriptions jd ON jd.id = i.jd_id WHERE i.id=%s AND i.user_id=%s",
            (interview_id, request.user['id'])
        )
        if not interview_row:
            return jsonify({"success": False, "message": "Interview not found"}), 404
        questions_rows = query_all(
            f"SELECT * FROM questions WHERE interview_id=%s ORDER BY {QUESTION_ORDER_SQL}", (interview_id,)
        )
        if not questions_rows and interview_row.get('resume_id') and interview_row.get('jd_id') and interview_row.get('question_set') is not None:
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
                    request.user['id'],
                    request.user['id'],
                )
            )
        job_title = interview_row['title'] or ''
        job_description = interview_row['description'] or ''
        questions = [dict(q) for q in questions_rows]

        seen = {}
        for q in questions:
            question_text = (q.get('question_text') or '').strip()
            if not question_text:
                continue
            key = question_text.lower()
            if key not in seen:
                seen[key] = {
                    "question_text": question_text,
                    "requires_code": bool(q.get('requires_code', False)),
                    "difficulty_level": normalize_question_difficulty(q.get('difficulty_level') or q.get('difficulty_category')),
                }
        core_questions = list(seen.values())

        dynamic_config = {
            "job_title": job_title,
            "job_description": job_description,
            "core_questions": core_questions,
            "coding_requirement": [],
            "time_limit_minutes": 150,
            "custom_questions": []
        }

        user_id = request.user['id']
        instance_key = f"{interview_id}:{user_id}"

        # Load or create manager using DB-backed session store
        config_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
                json.dump(dynamic_config, tf)
                config_path = tf.name

            saved_state = load_session(instance_key)
            manager = InterviewManager(config_path=config_path)
            if saved_state:
                manager.__dict__.update({
                    k: v for k, v in saved_state.items()
                    if not callable(v) and k not in ('model',)
                })
        finally:
            if config_path and os.path.exists(config_path):
                os.unlink(config_path)

        response = manager.receive_input(user_input)

        # Persist updated session state
        try:
            serializable = {
                k: v for k, v in manager.__dict__.items()
                if isinstance(v, (str, int, float, bool, list, dict, type(None)))
            }
            save_session(instance_key, serializable)
        except Exception as se:
            print(f"[WARN] Session save failed: {se}")

        # Save to chat history
        execute("INSERT INTO chat_history (interview_id, role, content) VALUES (%s,%s,%s)",
                (interview_id, 'user', user_input))

        if response.get("message"):
            execute("INSERT INTO chat_history (interview_id, role, content) VALUES (%s,%s,%s)",
                    (interview_id, 'assistant', response["message"]))

        # Generate audio for interviewer response
        audio_url = None
        if response.get("message") and not response.get("interview_done", False):
            try:
                response_text = response["message"]
                ts = datetime.now().strftime("%Y%m%dT%H%M%S")
                text_hash = hashlib.md5(response_text.encode()).hexdigest()[:8]
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
            try:
                merged_path = _merge_interview_audio(user_id, interview_id)
                merged_url = public_url(merged_path) if merged_path else None

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

                execute("UPDATE interviews SET status='ENDED' WHERE id=%s", (interview_id,))

                # Clean up per-turn audio files after successful merge
                if merged_path:
                    per_turn = [f for f in list_folder(f"audio/{user_id}/{interview_id}")
                                if f['name'].startswith(('interviewer_', 'user_'))]
                    delete_files([f['relative_path'] for f in per_turn])

                # Remove session from store
                delete_session(instance_key)
                feedback_saved = True
            except Exception as se:
                print(f"[ERROR] Save on completion failed: {se}")

        return jsonify({
            "success": True,
            "data": {
                "response": response.get("message", "Sorry, something went wrong."),
                "stage": response.get("stage", "unknown"),
                "interview_done": response.get("interview_done", False),
                "feedback_saved_successfully": feedback_saved,
                "audio_url": audio_url,
                "requires_code": response.get("requires_code")
            }
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# ─────────────────────────────────────────────────────────────────────────────
#  AUDIO MERGE HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _merge_interview_audio(user_id, interview_id):
    folder = f"audio/{user_id}/{interview_id}"
    files = list_folder(folder)
    if not files:
        return None
    audio_files = [f for f in files if f['name'].startswith(('interviewer_', 'user_'))]
    if not audio_files:
        return None
    audio_files.sort(key=lambda x: x['name'])
    segments = []
    temp_files = []
    try:
        for f in audio_files:
            data = read_bytes(f['relative_path'])
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tf:
                tf.write(data)
                temp_files.append(tf.name)
            segments.append(AudioSegment.from_wav(tf.name))
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
            "audio_url": result['public_url'],
            "file_size": result['file_size']
        }})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# ─────────────────────────────────────────────────────────────────────────────
#  SUPPORT BOT
# ─────────────────────────────────────────────────────────────────────────────

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
            model="llama3",
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
        return jsonify({"success": False, "message": "Support bot unavailable"}), 500

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
            result = analyze_performance_from_feedbacks(data['feedbacks'], data.get('model', 'llama3'))
        else:
            auth_token = request.headers.get('Authorization', '').split(' ')[-1]
            result = analyze_user_performance(auth_token, data.get('model', 'llama3'), data.get('limit', 100))
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
    r'importlib|ctypes|threading|multiprocessing)',
    _re.IGNORECASE
)


def _run_code(cmd, code, suffix, timeout=8):
    if len(code) > _CODE_SIZE_LIMIT:
        return jsonify({"success": False, "message": "Code too large (max 64 KB)"}), 400
    if _DANGER_PATTERNS.search(code) and suffix == '.py':
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
    try:
        if language == 'python':
            return _run_code(['python3'], code, '.py')
        elif language == 'javascript':
            return _run_code(['node'], code, '.js')
        elif language == 'java':
            with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False) as f:
                f.write(code); path = f.name
            try:
                c = subprocess.run(['javac', path], capture_output=True, text=True, timeout=10)
                if c.returncode != 0:
                    return jsonify({"success": True, "data": {"output": "", "error": c.stderr}})
                cls = os.path.splitext(os.path.basename(path))[0]
                r = subprocess.run(['java', '-cp', os.path.dirname(path), cls],
                                   capture_output=True, text=True, timeout=10)
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

@socketio.on('connect')
def handle_connect():
    emit('response', {'message': 'Connected to head tracking'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('frame')
def handle_frame(data):
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
        parts = re.split(r'(?:^|\n)\s*\d+\.\s*', text)
        points = [part.strip(" \n\t-•") for part in parts if part.strip(" \n\t-•")]
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
    storage_root = require_env("STORAGE_PATH")
    safe_root = os.path.abspath(storage_root)
    file_path = os.path.abspath(os.path.join(safe_root, relative_path))
    if not file_path.startswith(f"{safe_root}{os.sep}"):
        abort(404)
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        abort(404)
    return send_from_directory(safe_root, relative_path, as_attachment=False)


def _pairing_key(resume_id, jd_id):
    return f"{resume_id}:{jd_id}"


def _serialize_question(row):
    data = dict(row)
    difficulty = normalize_question_difficulty(data.get('difficulty_level') or data.get('difficulty_category'))
    data['difficulty_level'] = difficulty
    data['difficulty_category'] = difficulty
    data['difficulty_experience'] = data.get('difficulty_experience') or 'beginner'
    data['question'] = data.get('question_text')
    data['answer'] = data.get('expected_answer')
    return data


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
        for row in query_all("SELECT * FROM interview_feedback", ())
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
                'resumeUrl': resume.get('file_url') or public_url(resume.get('stored_path', '')) if resume.get('stored_path') else resume.get('file_url'),
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
            'audio_url': feedback.get('audio_url') if feedback else None,
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
    base = require_env("DOMAIN").rstrip('/')
    params = [
        f"interview_id={interview_id}",
        f"payment_id={payment_id}",
        f"status={status}",
    ]
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
    updates = []
    params = []
    full_name = data.get('full_name') or (data.get('data') or {}).get('full_name')
    username = data.get('username')
    password = data.get('password')
    if full_name is not None:
        updates.append('full_name=%s')
        params.append(full_name.strip())
    if username is not None:
        username = normalize_username(username)
        updates.append('username=%s')
        params.append(username)
    if password:
        updates.append('password_hash=%s')
        params.append(hash_password(password))
    if not updates:
        user = query_one('SELECT id, username, email, full_name, plan, created_at, email_verified_at FROM users WHERE id=%s', (request.user['id'],))
        return jsonify({'success': True, 'user': serialize_user(user)})
    params.append(request.user['id'])
    try:
        user = execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id=%s RETURNING id, username, email, full_name, plan, created_at, email_verified_at",
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
        return jsonify({'success': True, 'data': [dict(row) for row in rows]})
    data = request.get_json() or {}
    file_url = data.get('file_url')
    file_name = data.get('file_name') or 'resume'
    stored_path = data.get('stored_path')
    row = execute(
        'INSERT INTO resumes (user_id, file_url, file_name, stored_path) VALUES (%s, %s, %s, %s) RETURNING *',
        (user_id, file_url, file_name, stored_path),
    )
    return jsonify({'success': True, 'data': dict(row)}), 201


@app.route('/api/payments', methods=['GET'])
@verify_auth_token
def get_payments():
    rows = query_all('SELECT * FROM payments WHERE user_id=%s ORDER BY paid_at DESC', (request.user['id'],))
    return jsonify({'success': True, 'data': [dict(row) for row in rows]})


def _create_payment_impl():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    data = request.get_json() or {}
    user_id = request.user['id']
    interview_id = data.get('interview_id')
    resume_id = data.get('resume_id')
    jd_id = data.get('jd_id')
    question_set = data.get('question_set')
    retake_from = data.get('retake_from')
    amount = data.get('amount', 49900)
    payment_id = f"pay_{uuid.uuid4().hex[:12]}"

    if interview_id:
        execute(
            """
            UPDATE interviews
            SET resume_id = COALESCE(%s, resume_id),
                jd_id = COALESCE(%s, jd_id),
                question_set = COALESCE(%s, question_set),
                retake_from = COALESCE(%s, retake_from),
                status = 'STARTED'
            WHERE id = %s AND user_id = %s
            """,
            (resume_id, jd_id, question_set, retake_from, interview_id, user_id),
        )

    payment = execute(
        """
        INSERT INTO payments (user_id, interview_id, amount, provider, payment_status, transaction_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (user_id, interview_id, amount, 'internal', 'success', payment_id),
    )

    return jsonify({
        'success': True,
        'payment_id': payment_id,
        'payment_url': _payment_redirect_url(interview_id, payment_id, resume_id, jd_id, question_set, 'success'),
        'data': dict(payment) if payment else None,
    })


@app.route('/api/create-payment', methods=['POST', 'OPTIONS'])
@verify_auth_token
def create_payment():
    return _create_payment_impl()


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
    folder = (request.form.get('folder') or 'general').strip('/')
    filename = secure_filename(file.filename)
    result = save_bytes(file.read(), folder, filename)
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
    return _create_payment_impl()


@app.route('/functions/v1/interview-feedback', methods=['GET'])
@app.route('/api/functions/v1/interview-feedback', methods=['GET'])
@verify_auth_token
def legacy_interview_feedback():
    interview_id = request.args.get('interview_id')
    if interview_id:
        row = query_one('SELECT * FROM interview_feedback WHERE interview_id=%s', (interview_id,))
        if not row:
            return jsonify({'success': True, 'data': []})
        normalized = dict(row)
        normalized['metrics'] = _normalize_metrics(normalized.get('metrics'))
        normalized['key_strengths'] = _normalize_list(normalized.get('key_strengths'))
        normalized['improvement_areas'] = _normalize_list(normalized.get('improvement_areas'))
        return jsonify({'success': True, 'data': [normalized]})
    limit = int(request.args.get('limit', 100))
    rows = query_all(
        """
        SELECT f.*
        FROM interview_feedback f
        JOIN interviews i ON i.id = f.interview_id
        WHERE i.user_id=%s
        ORDER BY f.created_at ASC
        LIMIT %s
        """,
        (request.user['id'], limit),
    )
    return jsonify({'success': True, 'data': [dict(row) for row in rows]})


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
        return jsonify({'success': True, 'history': [{'content': content}] if content else []})
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
@verify_auth_token
def refresh_token():
    """Issue a fresh JWT for an already-authenticated user."""
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    user = query_one(
        'SELECT id, username, email, full_name, plan, created_at, email_verified_at FROM users WHERE id=%s',
        (request.user['id'],)
    )
    if not user:
        return jsonify({'error': 'User not found'}), 404
    token = create_token(str(user['id']), user['email'], user['full_name'], user['plan'])
    return jsonify({'token': token, 'user': serialize_user(user)})


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
        execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TIMESTAMPTZ NOT NULL,
                consumed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        # Invalidate old tokens
        execute(
            'UPDATE password_reset_tokens SET consumed_at=now() WHERE user_id=%s AND consumed_at IS NULL',
            (user['id'],)
        )
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        execute(
            "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES (%s,%s, now() + interval '1 hour')",
            (user['id'], token_hash)
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
        else:
            print(f"[WARN] SMTP not configured. Reset link for {user['email']}: {reset_link}")
            return jsonify({
                'message': 'SMTP is not configured, so use the reset link shown below.',
                'delivery': 'manual',
                'reset_link': reset_link,
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
    return jsonify({'message': 'Password updated successfully.', 'token': new_token})


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
        audio_files = list_folder(f'audio/{user_id}')
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
        "SELECT COUNT(*) AS cnt FROM interviews WHERE user_id=%s AND status='ENDED'", (user_id,)
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
        WHERE i.user_id=%s AND i.status='ENDED'
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
    if not _can_view_admin_logs(query_one('SELECT * FROM users WHERE id=%s', (request.user['id'],))):
        return jsonify({'error': 'Forbidden'}), 403
    hours = int((request.get_json() or {}).get('hours', 24))
    purge_old_sessions(hours)
    return jsonify({'success': True, 'message': f'Sessions older than {hours}h purged.'})

import atexit
from common.db import close_pool

atexit.register(close_pool)

print("[INFO] Scheduling AI warmup...")
schedule_background_ai_warmup()
print("[INFO] Backend ready")

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
