#!/usr/bin/env bash
# Apply post-certbot nginx config (fixes www → https redirect). Run after 09-code-enable-ssl.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

SSH="$(dirname "$0")/ssh-prod.sh"
CONF="$(dirname "$0")/../nginx/interviewcoach-prod-ssl.conf"
API_IP="${API_PUBLIC_IP:-${API_HOST#*@}}"

chmod +x "$SSH"
"$SSH" --scp "$CONF" "${SSH_USER}@${API_IP}:/tmp/interviewcoach-prod-ssl.conf"
"$SSH" bash -s <<'EOF'
set -euo pipefail
sudo cp /tmp/interviewcoach-prod-ssl.conf /etc/nginx/sites-available/interviewcoach-prod
sudo ln -sf /etc/nginx/sites-available/interviewcoach-prod /etc/nginx/sites-enabled/interviewcoach-prod
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
EOF
echo "SSL nginx config applied."
