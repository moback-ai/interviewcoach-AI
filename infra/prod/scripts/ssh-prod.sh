#!/usr/bin/env bash
# SSH helper — loads key from Secrets Manager if missing locally.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
SSH_KEY_SECRET="${SSH_KEY_SECRET:-interviewcoach/prod/ec2-ssh-key}"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/interviewcoach-key-v2.pem}"
SSH_USER="${SSH_USER:-ubuntu}"
API_IP="${API_PUBLIC_IP:-}"

if [[ -z "$API_IP" && -n "${API_HOST:-}" ]]; then
  API_IP="${API_HOST#*@}"
fi

if [[ ! -f "$SSH_KEY_PATH" ]]; then
  echo "Fetching SSH key → $SSH_KEY_PATH"
  mkdir -p "$(dirname "$SSH_KEY_PATH")"
  aws secretsmanager get-secret-value --region "$REGION" --secret-id "$SSH_KEY_SECRET" \
    --query SecretString --output text | python3 -c "
import json, sys, os
d = json.load(sys.stdin)
pem = d.get('pem', '').replace('\\\\n', '\n')
path = os.environ['OUT']
with open(path, 'w') as f:
    f.write(pem if pem.endswith('\n') else pem + '\n')
os.chmod(path, 0o600)
" OUT="$SSH_KEY_PATH"
fi

# Expand ~ in SSH_KEY_PATH for scripts that need a literal path
SSH_KEY_PATH="${SSH_KEY_PATH/#\~/$HOME}"
export SSH_OPTS=(-i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o ConnectTimeout=30)

if [[ "${1:-}" == "--scp" ]]; then
  shift
  scp "${SSH_OPTS[@]}" "$@"
elif [[ $# -gt 0 ]]; then
  exec ssh "${SSH_OPTS[@]}" "${SSH_USER}@${API_IP}" "$@"
else
  exec ssh "${SSH_OPTS[@]}" "${SSH_USER}@${API_IP}"
fi
