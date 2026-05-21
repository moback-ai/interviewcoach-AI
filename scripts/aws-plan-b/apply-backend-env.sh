#!/usr/bin/env bash
# Plan B: merge performance env into AWS Secrets Manager + restart backend (SSH)
#
# Usage:
#   ./apply-backend-env.sh              # dry-run
#   ./apply-backend-env.sh --apply
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.env"
[[ -f "${SCRIPT_DIR}/outputs.env" ]] && source "${SCRIPT_DIR}/outputs.env"

SSH_KEY="${SSH_KEY:-$HOME/.ssh/interviewcoach-deploy.pem}"
TARGET_HOST="${API_PUBLIC_IP:-$AI_PUBLIC_IP}"
SECRET_ID="${AWS_SECRETS_MANAGER_SECRET_ID:-interviewcoach/prod/app}"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

log() { echo "[$(date +%H:%M:%S)] $*"; }

merge_secret_locally() {
  local tmp
  tmp="$(mktemp)"
  aws secretsmanager get-secret-value \
    --region "$AWS_REGION" \
    --secret-id "$SECRET_ID" \
    --query SecretString --output text >"$tmp"
  python3 - "$tmp" <<'PY'
import json, sys
path = sys.argv[1]
with open(path) as f:
    data = json.load(f)
updates = {
    "QUESTION_GEN_FORCE_LOCAL": "true",
    "JD_PARSE_USE_OLLAMA": "false",
    "INTERVIEW_SERVER_TTS": "false",
    "INTERVIEW_FAST_WRAPUP": "true",
    "INTERVIEW_RESPONSE_TIMEOUT_SECONDS": "45",
    "QUESTION_GEN_OLLAMA_TIMEOUT_SECONDS": "90",
    "JD_PARSE_OLLAMA_TIMEOUT_SECONDS": "25",
    "OLLAMA_MODEL": "llama3.2:3b",
    "ENABLE_AI_WARMUP": "false",
    "WHISPER_BEAM_SIZE": "1",
    "OLLAMA_DIAGNOSTICS_CACHE_SECONDS": "30",
}
if OLLAMA_HOST := __import__("os").environ.get("OLLAMA_HOST", "").strip():
    updates["OLLAMA_HOST"] = OLLAMA_HOST
    updates["OLLAMA_HEALTH_URL"] = __import__("os").environ.get(
        "OLLAMA_HEALTH_URL", f"{OLLAMA_HOST}/api/tags"
    )
data.update(updates)
with open(path, "w") as f:
    json.dump(data, f)
print("Plan B keys merged into secret payload")
PY
  if [[ "$APPLY" -eq 1 ]]; then
    aws secretsmanager put-secret-value \
      --region "$AWS_REGION" \
      --secret-id "$SECRET_ID" \
      --secret-string "file://${tmp}"
    log "Secrets Manager updated: $SECRET_ID"
  else
    log "DRY-RUN: would put-secret-value for $SECRET_ID"
  fi
  rm -f "$tmp"
}

restart_backend() {
  if [[ "$APPLY" -ne 1 ]]; then
    log "DRY-RUN: would SSH ubuntu@${TARGET_HOST}, ollama pull, pm2 restart with secrets env"
    return
  fi
  ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "ubuntu@${TARGET_HOST}" \
    AWS_REGION="$AWS_REGION" \
    AWS_SECRETS_MANAGER_SECRET_ID="$SECRET_ID" \
    OLLAMA_MODEL="${OLLAMA_MODEL}" bash -s <<'REMOTE'
set -euo pipefail
command -v ollama >/dev/null && ollama pull "${OLLAMA_MODEL}" || true
pm2 delete backend >/dev/null 2>&1 || true
AWS_REGION="${AWS_REGION}" AWS_SECRETS_MANAGER_SECRET_ID="${AWS_SECRETS_MANAGER_SECRET_ID}" \
  pm2 start "cd /apps/backend/current && /apps/backend/venv/bin/gunicorn -w 1 --threads 8 -b 0.0.0.0:5000 --timeout 300 --max-requests 2000 --max-requests-jitter 200 app:app" --name backend
pm2 save
sleep 6
curl -fsS http://127.0.0.1:5000/api/health | python3 -m json.tool 2>/dev/null | head -25 || true
REMOTE
}

log "Target: ubuntu@${TARGET_HOST} | Secret: ${SECRET_ID}"
merge_secret_locally
restart_backend
log "Done."
