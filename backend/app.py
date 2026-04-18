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
from urllib.parse import urlencode

import soundfile as sf
import cv2
import numpy as np
import mediapipe as mp

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from PIL import Image, UnidentifiedImageError
from dotenv import load_dotenv
from datetime import datetime
from werkzeug.utils import secure_filename
from pydub import AudioSegment
import requests as http_requests

# ── Environment ───────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

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
interview_instances = {}

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv("MAX_CONTENT_MB", 200)) * 1024 * 1024

DOMAIN = os.getenv("DOMAIN", "http://localhost")
EMAIL_VERIFICATION_TTL_HOURS = int(os.getenv("EMAIL_VERIFICATION_TTL_HOURS", "24"))

CORS(app,
     supports_credentials=True,
     origins=[DOMAIN, "http://localhost:5173", "http://127.0.0.1:5173"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept"])

socketio = SocketIO(app, cors_allowed_origins="*")


def get_public_origin():
    return os.getenv("DOMAIN", DOMAIN).rstrip("/")


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

# ─────────────────────────────────────────────────────────────────────────────
#  HEAD TRACKING
# ─────────────────────────────────────────────────────────────────────────────

class EyeContactDetector_Callib:
    def __init__(self):
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


try:
    detector = EyeContactDetector_Callib()
    print("[INFO] Head tracking initialized")
except Exception as e:
    print(f"[ERROR] Head tracking failed: {e}")
    detector = None


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
    model_size = os.getenv("WHISPER_MODEL", "base")
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
            questions.append({
                "question_text": prompt,
                "expected_answer": expected,
                "difficulty_level": "medium" if difficulty == "coding" else difficulty,
                "difficulty_category": difficulty,
                "requires_code": difficulty == "coding",
            })

    return {
        "success": True,
        "candidate": candidate_name,
        "questions": questions,
        "questions_count": len(questions),
    }

# ─────────────────────────────────────────────────────────────────────────────
#  AUTH  (replaces the legacy hosted auth layer)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/signup', methods=['POST', 'OPTIONS'])
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
        row = execute(
            "INSERT INTO questions (interview_id, resume_id, jd_id, question_text, expected_answer, "
            "difficulty_level, question_set, requires_code) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (interview_id, data.get('resume_id'), data.get('jd_id'),
             q.get('question_text'), q.get('expected_answer'),
             q.get('difficulty_level', 'medium'), q.get('question_set', 1),
             q.get('requires_code', False))
        )
        saved.append(str(row['id']))
    return jsonify({"success": True, "data": {"saved": len(saved)}}), 201


@app.route('/api/questions/<interview_id>', methods=['GET'])
@verify_auth_token
def get_questions(interview_id):
    rows = query_all("SELECT * FROM questions WHERE interview_id=%s ORDER BY created_at", (interview_id,))
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
    interviews = query_all(
        "SELECT i.*, jd.title as job_title FROM interviews i "
        "LEFT JOIN job_descriptions jd ON jd.id=i.jd_id "
        "WHERE i.user_id=%s ORDER BY i.scheduled_at DESC",
        (user_id,)
    )
    feedbacks = query_all(
        "SELECT f.* FROM interview_feedback f "
        "JOIN interviews i ON i.id=f.interview_id WHERE i.user_id=%s",
        (user_id,)
    )
    return jsonify({
        "success": True,
        "data": {
            "interviews": [dict(r) for r in interviews],
            "feedbacks": [dict(r) for r in feedbacks],
            "total_interviews": len(interviews)
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
        if resume_url.startswith(os.getenv("PUBLIC_STORAGE_URL", "")):
            # Local storage file
            relative = resume_url.replace(os.getenv("PUBLIC_STORAGE_URL", ""), "").lstrip("/")
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
            question_counts = data.get('question_counts', {'beginner': 2, 'medium': 2, 'hard': 2})
            try:
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
                    blend_pct_jd=data.get('blend_pct_jd', 50)
                )
            except Exception as pipeline_error:
                print(f"[WARN] Falling back to local question generator: {pipeline_error}")
                resume_text = extract_text_from_uploaded_document(temp_resume, ext)
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
@verify_auth_token
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

        # Fetch interview data from our own API
        resp = http_requests.get(
            "http://127.0.0.1:5000/api/interview-data",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"interview_id": interview_id},
            timeout=10
        )
        if resp.status_code != 200:
            return jsonify({"success": False, "message": "Failed to fetch interview data"}), 500

        result = resp.json()
        if not result.get('success'):
            return jsonify({"success": False, "message": "Interview data error"}), 500

        interview_data = result['data']
        job_title = interview_data['job_description']['title']
        job_description = interview_data['job_description']['description']
        questions = interview_data['questions']

        seen = set()
        core_questions = []
        for q in questions:
            if q['question_text'] not in seen:
                seen.add(q['question_text'])
                core_questions.append(q['question_text'])
        coding_requirement = [q['requires_code'] for q in questions]

        dynamic_config = {
            "job_title": job_title,
            "job_description": job_description,
            "core_questions": core_questions,
            "coding_requirement": coding_requirement,
            "time_limit_minutes": 150,
            "custom_questions": []
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
            json.dump(dynamic_config, tf)
            config_path = tf.name

        user_id = request.user['id']
        instance_key = f"{interview_id}:{user_id}"
        if instance_key not in interview_instances:
            interview_instances[instance_key] = InterviewManager(config_path=config_path)

        manager = interview_instances[instance_key]
        response = manager.receive_input(user_input)

        # Save to chat history
        execute("INSERT INTO chat_history (interview_id, role, content) VALUES (%s,%s,%s)",
                (interview_id, 'user', user_input))

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
                os.unlink(temp_audio)

                # Save AI response to chat history
                execute("INSERT INTO chat_history (interview_id, role, content) VALUES (%s,%s,%s)",
                        (interview_id, 'assistant', response_text))
            except Exception as ae:
                print(f"[WARN] Audio generation failed: {ae}")

        # Handle interview completion
        feedback_saved = False
        if response.get("interview_done", False):
            try:
                merged_path = _merge_interview_audio(user_id, interview_id)
                merged_url = public_url(merged_path) if merged_path else None

                transcript_resp = http_requests.post(
                    "http://127.0.0.1:5000/api/transcripts",
                    headers={"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"},
                    json={
                        "interview_id": interview_id,
                        "full_transcript": json.dumps(manager.conversation_history),
                        "evaluation_data": manager.final_evaluation_log
                    }
                )
                if transcript_resp.status_code in [200, 201]:
                    feedback_resp = http_requests.post(
                        "http://127.0.0.1:5000/api/interview-feedback",
                        headers={"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"},
                        json={
                            "interview_id": interview_id,
                            "summary": manager.final_summary,
                            "key_strengths": manager.key_strengths,
                            "improvement_areas": manager.improvement_areas,
                            "metrics": manager.metrics,
                            "audio_url": merged_url
                        }
                    )
                    if feedback_resp.status_code in [200, 201]:
                        execute("UPDATE interviews SET status='ENDED' WHERE id=%s", (interview_id,))
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
            "conversation_length": response.get("conversation_length", 0)
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
@verify_auth_token
def overall_performance():
    user_id = request.user['id']
    rows = query_all("SELECT * FROM overall_evaluation WHERE user_id=%s ORDER BY created_at DESC LIMIT 10",
                     (user_id,))
    return jsonify({"success": True, "data": [dict(r) for r in rows]})

# ─────────────────────────────────────────────────────────────────────────────
#  CODE EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

def _run_code(cmd, code, suffix, timeout=10):
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
        f.write(code)
        path = f.name
    try:
        result = subprocess.run(cmd + [path], capture_output=True, text=True, timeout=timeout)
        return jsonify({"success": True, "data": {
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }})
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "message": "Code execution timed out"}), 408
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
        if detector is None:
            emit("response", {"error": "Detector unavailable"})
            return
        result = detector.process(frame, is_calibrating=calibrate)
        emit("response", result)
    except Exception as e:
        emit("response", {"error": str(e)})

@socketio.on('reset_calibration')
def handle_reset_calibration():
    try:
        detector.reset_calibration()
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
    if isinstance(value, list):
        return value
    if not value:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [value]
        except Exception:
            return [value]
    return [value]


def _pairing_key(resume_id, jd_id):
    return f"{resume_id}:{jd_id}"


def _serialize_question(row):
    data = dict(row)
    difficulty = data.get('difficulty_level') or data.get('difficulty_category') or 'medium'
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
    base = DOMAIN.rstrip('/')
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
        sql += ' ORDER BY created_at ASC'
        rows = [_serialize_question(row) for row in query_all(sql, tuple(params))]
        return jsonify({'success': True, 'data': rows})
    data = request.get_json() or {}
    resume_id = data.get('resume_id')
    jd_id = data.get('jd_id')
    question_set = data.get('question_set', 1)
    saved = []
    for question in data.get('questions', []):
        row = execute(
            """
            INSERT INTO questions (interview_id, resume_id, jd_id, question_text, expected_answer, difficulty_level, question_set, requires_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                question.get('interview_id') or data.get('interview_id'),
                resume_id,
                jd_id,
                question.get('question_text') or question.get('question'),
                question.get('expected_answer') or question.get('answer'),
                question.get('difficulty_category') or question.get('difficulty_level') or 'medium',
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
        return jsonify({'success': True, 'data': [dict(row)] if row else []})
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

print("[INFO] Initializing Whisper model...")
initialize_whisper()
print("[INFO] Backend ready")

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
