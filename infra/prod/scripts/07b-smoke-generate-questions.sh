#!/usr/bin/env bash
# Smoke test: POST /api/generate-questions through public URL (validates CloudFront + ALB timeouts).
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh" 2>/dev/null || true

BASE_URL="${SMOKE_BASE_URL:-https://www.ugaanlabs.ai}"
SECRET_ID="${AWS_SECRETS_MANAGER_SECRET_ID:-interviewcoach/prod/app}"
REGION="${AWS_REGION:-ap-south-1}"
ATTEMPTS="${SMOKE_GEN_ATTEMPTS:-5}"
SLEEP="${SMOKE_GEN_SLEEP_SEC:-20}"
TIMEOUT_SEC="${SMOKE_GEN_TIMEOUT_SEC:-130}"

echo "=== generate-questions smoke test via $BASE_URL ==="

RESUME_TMP=$(mktemp -t ic-smoke-resume)
PAYLOAD_TMP=$(mktemp -t ic-smoke-payload)
trap 'rm -f "$RESUME_TMP" "$PAYLOAD_TMP"' EXIT

cat >"$RESUME_TMP" <<'RESUME'
Jane Smith
Senior Software Engineer | Bangalore

Summary: Full-stack engineer with 6 years building Python/Flask APIs, React dashboards, and AWS deployments.

Experience:
- Led migration of monolith to containerized services on ECS and ASG (2022-2025)
- Built interview coaching platform with Bedrock LLM integration and Redis queues
- Optimized PostgreSQL queries and added connection pooling for 10k daily users

Skills: Python, JavaScript, React, AWS, Docker, PostgreSQL, Redis, CI/CD

Education: B.Tech Computer Science, IIT
RESUME

BUCKET="${STT_S3_BUCKET:-ic-user-files-prod}"
S3_KEY="resumes/smoke-test/resume-$(date +%s).txt"
aws s3 cp "$RESUME_TMP" "s3://${BUCKET}/${S3_KEY}" --region "$REGION" >/dev/null
RESUME_URL="https://www.ugaanlabs.ai/api/files/${S3_KEY}"
echo "Resume files URL: $RESUME_URL"

export SECRET_ID REGION
SMOKE_VENV=$(mktemp -d /tmp/ic-smoke-venv.XXXXXX)
python3 -m venv "$SMOKE_VENV"
"$SMOKE_VENV/bin/pip" install -q PyJWT
TOKEN=$("$SMOKE_VENV/bin/python" <<'PY'
import json, os, subprocess
from datetime import datetime, timedelta
import jwt

secret_id = os.environ["SECRET_ID"]
region = os.environ["REGION"]
raw = subprocess.check_output([
    "aws", "secretsmanager", "get-secret-value",
    "--secret-id", secret_id,
    "--region", region,
    "--query", "SecretString",
    "--output", "text",
], text=True)
secret = json.loads(raw)
payload = {
    "user_id": "smoke-test",
    "email": "smoke@test.local",
    "full_name": "Smoke Test",
    "plan": "basic",
    "exp": datetime.utcnow() + timedelta(hours=1),
}
print(jwt.encode(payload, secret["JWT_SECRET"], algorithm="HS256"))
PY
)
rm -rf "$SMOKE_VENV"

python3 - "$RESUME_URL" "$PAYLOAD_TMP" <<'PY'
import json, sys
resume_url, out = sys.argv[1:3]
payload = {
    "resume_url": resume_url,
    "job_title": "Software Engineer",
    "job_description": (
        "We are hiring a software engineer with Python, AWS, and React experience "
        "to build scalable APIs and customer-facing dashboards."
    ),
    "question_counts": {"beginner": 1, "medium": 1, "hard": 1, "coding": 0},
    "include_answers": False,
}
with open(out, "w") as f:
    json.dump(payload, f)
PY

for i in $(seq 1 "$ATTEMPTS"); do
  echo "--- attempt $i/$ATTEMPTS ---"
  START=$(date +%s)
  HTTP_CODE=$(curl -sS -o /tmp/ic-smoke-gen.json -w '%{http_code}' \
    --max-time "$TIMEOUT_SEC" \
    -X POST "${BASE_URL}/api/generate-questions" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d @"$PAYLOAD_TMP" || echo "000")
  ELAPSED=$(( $(date +%s) - START ))
  echo "HTTP $HTTP_CODE in ${ELAPSED}s"

  if [[ "$HTTP_CODE" == "200" ]]; then
    python3 <<'PY'
import json
with open("/tmp/ic-smoke-gen.json") as f:
    data = json.load(f)
assert data.get("success"), data
questions = data.get("questions") or (data.get("data") or {}).get("questions") or []
assert len(questions) >= 1, data
print(f"OK: generated {len(questions)} question(s) in success response")
for q in questions[:3]:
    print(" -", (q.get("question_text") or q.get("question") or q.get("text") or str(q))[:120])
PY
    exit 0
  fi

  if [[ "$HTTP_CODE" == "504" ]]; then
    echo "504 gateway timeout — CloudFront may still be propagating or origin timeout too low"
  elif [[ -f /tmp/ic-smoke-gen.json ]]; then
    head -c 500 /tmp/ic-smoke-gen.json; echo
  fi
  sleep "$SLEEP"
done

echo "generate-questions smoke test FAILED after $ATTEMPTS attempts"
exit 1
