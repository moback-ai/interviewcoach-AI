#!/usr/bin/env bash
# Build frontend and sync to S3 — GitHub Actions ONLY (npm on runner).
set -euo pipefail

if [[ "${GITHUB_ACTIONS:-}" != "true" ]]; then
  echo "ERROR: Prod frontend builds run only on GitHub Actions."
  echo "  Actions → Deploy PROD → Run workflow"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm is required (install Node on the CI runner)."
  exit 1
fi

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
STATIC_BUCKET="${STATIC_BUCKET:?Set STATIC_BUCKET in prod.env}"
CF_DIST_ID="${CF_DIST_ID:-}"
DOMAIN="${FRONTEND_DOMAIN:-www.ugaanlabs.ai}"

cd "$ROOT/frontend"
export VITE_API_BASE_URL="https://${DOMAIN}/api"
export VITE_STORAGE_URL="https://${DOMAIN}/storage"
npm ci
npm run build
aws s3 sync dist/ "s3://${STATIC_BUCKET}/" --delete --region "${AWS_REGION:-ap-south-1}"

if [[ -n "$CF_DIST_ID" ]]; then
  aws cloudfront create-invalidation --distribution-id "$CF_DIST_ID" --paths "/*"
fi

echo "Frontend synced to s3://${STATIC_BUCKET}/"
