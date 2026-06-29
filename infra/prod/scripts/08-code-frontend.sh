#!/usr/bin/env bash
# Build frontend and upload to S3 (+ optional CloudFront invalidation).
# Builds on EC2 when local npm is unavailable.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SSH="$(dirname "$0")/ssh-prod.sh"
STATIC_BUCKET="${STATIC_BUCKET:?Set STATIC_BUCKET in prod.env}"
CF_DIST_ID="${CF_DIST_ID:-}"
DOMAIN="${FRONTEND_DOMAIN:-ugaanlabs.ai}"
API_IP="${API_PUBLIC_IP:-${API_HOST#*@}}"

chmod +x "$SSH"

if command -v npm >/dev/null 2>&1; then
  cd "$ROOT/frontend"
  export VITE_API_BASE_URL="https://${DOMAIN}/api"
  export VITE_STORAGE_URL="https://${DOMAIN}/storage"
  npm ci
  npm run build
  aws s3 sync dist/ "s3://${STATIC_BUCKET}/" --delete --region "${AWS_REGION:-ap-south-1}"
else
  echo "Local npm missing — building frontend on EC2 ..."
  tar czf - -C "$ROOT" --exclude='frontend/node_modules' --exclude='frontend/dist' frontend \
    | "$SSH" "mkdir -p /tmp/ic-fe-build && tar xzf - -C /tmp/ic-fe-build"
  "$SSH" bash -s <<EOF
set -euo pipefail
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
cd /tmp/ic-fe-build/frontend
export VITE_API_BASE_URL="https://${DOMAIN}/api"
export VITE_STORAGE_URL="https://${DOMAIN}/storage"
npm ci
npm run build
aws s3 sync dist/ s3://${STATIC_BUCKET}/ --delete --region ${AWS_REGION:-ap-south-1}
EOF
fi

if [[ -n "$CF_DIST_ID" ]]; then
  aws cloudfront create-invalidation --distribution-id "$CF_DIST_ID" --paths "/*"
fi

echo "Frontend synced to s3://${STATIC_BUCKET}/"
