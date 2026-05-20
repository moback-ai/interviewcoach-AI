#!/usr/bin/env bash
# Clone /apps/backend from AI host onto new API host and start gunicorn (after --split-api)
#
# Usage:
#   ./bootstrap-api-server.sh           # dry-run
#   ./bootstrap-api-server.sh --apply
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.env"
[[ -f "${SCRIPT_DIR}/outputs.env" ]] || { echo "Missing outputs.env — run plan-b-setup.sh --apply --split-api first"; exit 1; }
source "${SCRIPT_DIR}/outputs.env"

SSH_KEY="${SSH_KEY:-$HOME/.ssh/interviewcoach-deploy.pem}"
SECRET_ID="${AWS_SECRETS_MANAGER_SECRET_ID:-interviewcoach/prod/app}"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

if [[ "$APPLY" -ne 1 ]]; then
  log "DRY-RUN: would rsync /apps/backend from ${AI_PRIVATE_IP} -> API ${API_PUBLIC_IP} and start pm2"
  exit 0
fi

log "Bootstrapping API ${API_PUBLIC_IP} from AI ${AI_PRIVATE_IP}..."

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "ubuntu@${API_PUBLIC_IP}" \
  AI_PRIVATE_IP="${AI_PRIVATE_IP}" \
  AI_PUBLIC_IP="${AI_PUBLIC_IP}" \
  AWS_REGION="${AWS_REGION}" \
  SECRET_ID="${SECRET_ID}" \
  SSH_KEY_PATH="/tmp/deploy_key.pem" bash -s <<'REMOTE'
set -euo pipefail
sudo mkdir -p /apps/logs/live /apps/storage
sudo chown -R ubuntu:ubuntu /apps

# Copy deploy key from local (injected next) — use AI public IP for rsync source
if [[ ! -d /apps/backend/current ]]; then
  mkdir -p ~/.ssh && chmod 700 ~/.ssh
fi
REMOTE

scp -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_KEY" "ubuntu@${API_PUBLIC_IP}:/tmp/deploy_key.pem"
ssh -i "$SSH_KEY" "ubuntu@${API_PUBLIC_IP}" chmod 600 /tmp/deploy_key.pem

ssh -i "$SSH_KEY" "ubuntu@${API_PUBLIC_IP}" \
  AI_PRIVATE_IP="${AI_PRIVATE_IP}" AWS_REGION="${AWS_REGION}" SECRET_ID="${SECRET_ID}" bash -s <<'REMOTE'
set -euo pipefail
mkdir -p /apps/backend/releases /apps/logs/live /apps/storage
RELEASE_PATH=$(ssh -i /tmp/deploy_key.pem -o StrictHostKeyChecking=no ubuntu@${AI_PRIVATE_IP} \
  'readlink -f /apps/backend/current')
RELEASE_ID=$(basename "$RELEASE_PATH")
echo "Syncing release ${RELEASE_ID}..."
rsync -az -e "ssh -i /tmp/deploy_key.pem -o StrictHostKeyChecking=no" \
  "ubuntu@${AI_PRIVATE_IP}:${RELEASE_PATH}/" "/apps/backend/releases/${RELEASE_ID}/"
ln -sfn "/apps/backend/releases/${RELEASE_ID}" /apps/backend/current
rsync -az -e "ssh -i /tmp/deploy_key.pem -o StrictHostKeyChecking=no" \
  ubuntu@${AI_PRIVATE_IP}:/apps/storage/ /apps/storage/ 2>/dev/null || true
if [[ ! -x /apps/backend/venv/bin/gunicorn ]]; then
  echo "Creating API venv (pip install)..."
  python3 -m venv /apps/backend/venv
  /apps/backend/venv/bin/pip install -q --upgrade pip
  /apps/backend/venv/bin/pip install -q -r /apps/backend/current/requirements.txt
fi
pm2 delete backend >/dev/null 2>&1 || true
AWS_REGION="${AWS_REGION}" AWS_SECRETS_MANAGER_SECRET_ID="${SECRET_ID}" \
  pm2 start "cd /apps/backend/current && /apps/backend/venv/bin/gunicorn -w 2 --threads 4 -b 0.0.0.0:5000 --timeout 120 app:app" --name backend
pm2 save
sleep 6
curl -fsS http://127.0.0.1:5000/api/health | python3 -m json.tool | head -20
REMOTE

log "API bootstrap complete."
