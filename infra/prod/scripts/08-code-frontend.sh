#!/usr/bin/env bash
# Build frontend and sync to S3 + CloudFront invalidation.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

STATIC_BUCKET="${STATIC_BUCKET:?Set STATIC_BUCKET}"
CF_DIST_ID="${CF_DIST_ID:-}"

command -v npm >/dev/null || { echo "npm required"; exit 1; }

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT/frontend"

cat > .env <<EOF
VITE_API_BASE_URL=/api
VITE_STORAGE_URL=/storage
EOF

npm ci --legacy-peer-deps --prefer-offline --no-audit
npm run build

echo "Syncing to s3://${STATIC_BUCKET}/ ..."
aws s3 sync dist/ "s3://${STATIC_BUCKET}/" --delete

if [[ -n "$CF_DIST_ID" ]]; then
  echo "Invalidating CloudFront ${CF_DIST_ID} ..."
  aws cloudfront create-invalidation --distribution-id "$CF_DIST_ID" --paths "/*" >/dev/null
fi

echo "Frontend deploy done."
