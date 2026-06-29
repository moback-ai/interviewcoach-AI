#!/usr/bin/env bash
# Step 5 — Build frontend and upload to S3 + CloudFront invalidation.
# Usage: STATIC_BUCKET=ic-static-prod CF_DIST_ID=E123 ./05-frontend-s3-cloudfront.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
STATIC_BUCKET="${STATIC_BUCKET:?Set STATIC_BUCKET in prod.env}"
CF_DIST_ID="${CF_DIST_ID:-}"

cd "$ROOT/frontend"
npm ci
npm run build

aws s3 sync dist/ "s3://${STATIC_BUCKET}/" --delete

if [[ -n "$CF_DIST_ID" ]]; then
  aws cloudfront create-invalidation --distribution-id "$CF_DIST_ID" --paths "/*"
fi

echo "Step 5 complete. Static assets in s3://${STATIC_BUCKET}/"
