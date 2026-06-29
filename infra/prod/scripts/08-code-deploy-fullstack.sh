#!/usr/bin/env bash
# Phase 3 — Deploy frontend + nginx on prod EC2 (full stack behind ugaanlabs.ai).
# Builds React on EC2, serves static via nginx, proxies /api and /socket.io to Docker API.
#
# Usage: bash infra/prod/scripts/08-code-deploy-fullstack.sh
# After DNS A record → API_PUBLIC_IP: bash infra/prod/scripts/09-code-enable-ssl.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SSH="$(dirname "$0")/ssh-prod.sh"
NGINX_CONF="$(dirname "$0")/../nginx/interviewcoach-prod.conf"
DOMAIN="${FRONTEND_DOMAIN:-ugaanlabs.ai}"
API_IP="${API_PUBLIC_IP:-${API_HOST#*@}}"

chmod +x "$SSH"

if [[ ! -f "$NGINX_CONF" ]]; then
  echo "Missing nginx config: $NGINX_CONF"
  exit 1
fi

echo "Packaging frontend → EC2 ..."
tar czf - \
  -C "$ROOT" \
  --exclude='frontend/node_modules' \
  --exclude='frontend/dist' \
  frontend \
  | "$SSH" "mkdir -p /tmp/ic-fe-build && tar xzf - -C /tmp/ic-fe-build"

echo "Uploading nginx site config ..."
"$SSH" --scp "$NGINX_CONF" "${SSH_USER}@${API_IP}:/tmp/interviewcoach-prod.conf"

echo "Installing packages, building frontend, configuring nginx ..."
"$SSH" bash -s <<EOF
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

if ! command -v node >/dev/null 2>&1 || [[ "\$(node -v 2>/dev/null || echo v0)" < "v22" ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx

cd /tmp/ic-fe-build/frontend
export VITE_API_BASE_URL="https://${DOMAIN}/api"
export VITE_STORAGE_URL="https://${DOMAIN}/storage"
npm ci
npm run build

sudo mkdir -p /var/www/interview
sudo rm -rf /var/www/interview/*
sudo cp -r dist/* /var/www/interview/
sudo chown -R www-data:www-data /var/www/interview

sudo cp /tmp/interviewcoach-prod.conf /etc/nginx/sites-available/interviewcoach-prod
sudo ln -sf /etc/nginx/sites-available/interviewcoach-prod /etc/nginx/sites-enabled/interviewcoach-prod
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

echo "Smoke (local nginx → API):"
curl -fsS http://127.0.0.1/api/health | head -c 200
echo ""
EOF

echo ""
echo "Phase 3 fullstack deploy complete."
echo "  HTTP smoke:  http://${API_IP}/api/health"
echo "  Frontend:    http://${API_IP}/"
echo ""
echo "DNS cutover: set A record for ${DOMAIN} (and www) → ${API_IP}"
echo "Then run: bash infra/prod/scripts/09-code-enable-ssl.sh"
echo "After SSL:  bash infra/prod/scripts/09-code-apply-ssl-nginx.sh"
