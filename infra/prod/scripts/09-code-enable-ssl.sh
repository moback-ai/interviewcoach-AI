#!/usr/bin/env bash
# Enable HTTPS on prod EC2 after DNS A record points to API_PUBLIC_IP.
# Usage: bash infra/prod/scripts/09-code-enable-ssl.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

SSH="$(dirname "$0")/ssh-prod.sh"
DOMAIN="${FRONTEND_DOMAIN:-ugaanlabs.ai}"
API_IP="${API_PUBLIC_IP:-${API_HOST#*@}}"
EMAIL="${SSL_ADMIN_EMAIL:-no-reply@${DOMAIN}}"

chmod +x "$SSH"

echo "Checking DNS for ${DOMAIN} → ${API_IP} ..."
RESOLVED=$(dig +short "${DOMAIN}" A | head -1)
if [[ "$RESOLVED" != "${API_IP}" ]]; then
  echo "DNS not ready: ${DOMAIN} resolves to '${RESOLVED}' (expected ${API_IP})"
  echo "Update your registrar A record, wait a few minutes, then re-run this script."
  exit 1
fi

"$SSH" bash -s <<EOF
set -euo pipefail
sudo certbot --nginx \
  -d ${DOMAIN} \
  -d www.${DOMAIN} \
  --non-interactive \
  --agree-tos \
  -m ${EMAIL} \
  --redirect
sudo nginx -t
sudo systemctl reload nginx
curl -fsS https://${DOMAIN}/api/health | head -c 300
echo ""
EOF

bash "$(dirname "$0")/09-code-apply-ssl-nginx.sh"

echo "HTTPS enabled for https://${DOMAIN}"
