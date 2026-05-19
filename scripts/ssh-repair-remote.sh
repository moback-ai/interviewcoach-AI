#!/usr/bin/env bash
# Usage (from repo root):
#   bash scripts/setup-ssh-key-from-aws.sh
#   bash scripts/ssh-repair-remote.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EC2_HOST="${EC2_HOST:-13.200.28.73}"
EC2_USER="${EC2_USER:-ubuntu}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/interviewcoach-deploy.pem}"

if [ ! -f "$SSH_KEY" ]; then
  echo "SSH key not found: $SSH_KEY"
  echo "Run first: bash \"$ROOT/scripts/setup-ssh-key-from-aws.sh\""
  exit 1
fi

chmod 400 "$SSH_KEY"
SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15)

echo "Repairing backend at ${EC2_USER}@${EC2_HOST} ..."
ssh "${SSH_OPTS[@]}" "${EC2_USER}@${EC2_HOST}" 'bash -s' < "$ROOT/scripts/server-repair.sh"

echo "Public health check:"
curl -fsS "https://ugaanlabs.ai/api/health" | python3 -m json.tool
