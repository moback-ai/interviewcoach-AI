#!/usr/bin/env bash
# Run from your Mac after setting EC2 credentials:
#   export EC2_HOST=3.110.248.130
#   export EC2_USER=ubuntu
#   export SSH_KEY="$HOME/.ssh/interviewcoach-deploy.pem"
#   bash scripts/ssh-repair-remote.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EC2_HOST="${EC2_HOST:?Set EC2_HOST to your backend public IP or hostname}"
EC2_USER="${EC2_USER:-ubuntu}"
SSH_KEY="${SSH_KEY:?Set SSH_KEY to your EC2 .pem path}"

if [ ! -f "$SSH_KEY" ]; then
  echo "SSH key not found: $SSH_KEY"
  exit 1
fi

chmod 400 "$SSH_KEY"
SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15)

echo "Repairing backend at ${EC2_USER}@${EC2_HOST} ..."
ssh "${SSH_OPTS[@]}" "${EC2_USER}@${EC2_HOST}" 'bash -s' < "$ROOT/scripts/server-repair.sh"

echo "Public health check:"
curl -fsS "https://ugaanlabs.ai/api/health" | python3 -m json.tool
