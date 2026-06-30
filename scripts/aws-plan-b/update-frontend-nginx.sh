#!/usr/bin/env bash
# Point frontend nginx /api proxy at the dedicated API server (after --split-api)
#
# Usage:
#   export API_PUBLIC_IP=1.2.3.4
#   ./update-frontend-nginx.sh           # dry-run
#   ./update-frontend-nginx.sh --apply   # SSH and patch nginx on frontend
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.env"
[[ -f "${SCRIPT_DIR}/outputs.env" ]] && source "${SCRIPT_DIR}/outputs.env"

API_PUBLIC_IP="${API_PUBLIC_IP:-}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/interviewcoach-deploy.pem}"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

if [[ -z "$API_PUBLIC_IP" ]]; then
  echo "Set API_PUBLIC_IP in outputs.env or environment (from plan-b-setup.sh --split-api)"
  exit 1
fi

REMOTE_SCRIPT=$(cat <<EOS
set -e
API_PRIVATE="${API_PRIVATE_IP}"
if [[ -z "\$API_PRIVATE" ]]; then
  echo "Set API_PRIVATE_IP in outputs.env"
  exit 1
fi
CONF=/etc/nginx/sites-enabled/interview
if [[ ! -f "\$CONF" ]]; then
  CONF=\$(grep -rl "proxy_pass.*5001" /etc/nginx/sites-enabled 2>/dev/null | head -1)
fi
echo "Patching \$CONF -> http://\${API_PRIVATE}:5000"
sudo sed -i.bak-planb -E \
  "s|proxy_pass http://[^;]+:5001/|proxy_pass http://\${API_PRIVATE}:5000/|g; \
   s|proxy_pass http://[^;]+:5000/|proxy_pass http://\${API_PRIVATE}:5000/|g" "\$CONF"
sudo nginx -t
sudo systemctl reload nginx
echo "Done."
EOS
)

echo "Frontend: ${FRONTEND_PUBLIC_IP}"
echo "New API upstream: http://${API_PUBLIC_IP}:5000"

if [[ "$APPLY" -eq 1 ]]; then
  ssh -i "$SSH_KEY" -o StrictHostKeyChecking=accept-new "ubuntu@${FRONTEND_PUBLIC_IP}" "$REMOTE_SCRIPT"
else
  echo "DRY-RUN SSH command:"
  echo "ssh -i $SSH_KEY ubuntu@${FRONTEND_PUBLIC_IP} '...'"
fi
