# InterviewCoach API + optional Whisper sidecar (same image, different CMD).
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY backend/ .

# API default; override for transcribe sidecar (see compose).
EXPOSE 5000 5001

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${HEALTH_PORT:-5000}/api/health" || exit 1

CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:5000", \
     "--timeout", "300", "--max-requests", "2000", "--max-requests-jitter", "200", "app:app"]
