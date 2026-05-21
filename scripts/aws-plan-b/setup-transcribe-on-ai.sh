#!/usr/bin/env bash
# Plan B: run Whisper transcribe sidecar on the AI host (same box as Ollama — no extra EC2).
#
# Usage:
#   ./setup-transcribe-on-ai.sh           # dry-run
#   ./setup-transcribe-on-ai.sh --apply
#
# After apply, run apply-backend-env.sh --apply so API gets TRANSCRIBE_SERVICE_URL.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.env"
[[ -f "${SCRIPT_DIR}/outputs.env" ]] && source "${SCRIPT_DIR}/outputs.env"

SSH_KEY="${SSH_KEY:-$HOME/.ssh/interviewcoach-deploy.pem}"
AI_HOST="${AI_PUBLIC_IP:-}"
AI_PRIVATE="${AI_PRIVATE_IP:-$AI_HOST}"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1
PORT="${TRANSCRIBE_SIDECAR_PORT:-5001}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

if [[ -z "$AI_HOST" ]]; then
  echo "Set AI_PUBLIC_IP in outputs.env (run optimize-550.sh first)." >&2
  exit 1
fi

log "AI host: ubuntu@${AI_HOST} | sidecar port ${PORT} | private ${AI_PRIVATE}"

if [[ "$APPLY" -ne 1 ]]; then
  log "DRY-RUN: would install pm2 transcribe sidecar and set TRANSCRIBE_SERVICE_URL=http://${AI_PRIVATE}:${PORT}"
  exit 0
fi

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "ubuntu@${AI_HOST}" \
  REPO_ROOT="/apps/backend/current" \
  PORT="$PORT" bash -s <<'REMOTE'
set -euo pipefail
cd "${REPO_ROOT}/.."
# repo layout: /apps/backend/current is backend; scripts at repo root
ROOT="$(dirname "$(dirname "${REPO_ROOT}")")/interviewcoach-AI" 2>/dev/null || true
if [[ ! -f "${REPO_ROOT}/../scripts/run-transcribe-sidecar.sh" ]]; then
  ROOT="/home/ubuntu/interviewcoach-AI"
fi
SCRIPT="${REPO_ROOT}/../../scripts/run-transcribe-sidecar.sh"
if [[ ! -f "$SCRIPT" ]]; then
  SCRIPT="$(find /home/ubuntu /apps -name run-transcribe-sidecar.sh 2>/dev/null | head -1)"
fi
export TRANSCRIBE_SIDECAR_PORT="${PORT}"
pm2 delete transcribe >/dev/null 2>&1 || true
pm2 start bash --name transcribe -- -lc "cd ${REPO_ROOT} && source venv/bin/activate && export TRANSCRIBE_SIDECAR_PORT=${PORT} && python -c \"
from app import app
app.run(host='0.0.0.0', port=int('${PORT}'), threaded=True)
\""
pm2 save
curl -fsS "http://127.0.0.1:${PORT}/api/health" | head -5 || echo "Sidecar started (health may require auth route)"
REMOTE

log "Set TRANSCRIBE_SERVICE_URL=http://${AI_PRIVATE}:${PORT} then apply-backend-env.sh --apply"
export AI_PRIVATE_IP="${AI_PRIVATE}"
export TRANSCRIBE_SERVICE_URL="http://${AI_PRIVATE}:${PORT}"
"${SCRIPT_DIR}/apply-backend-env.sh" --apply
