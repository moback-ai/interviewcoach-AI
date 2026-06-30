#!/usr/bin/env bash
# Set GitHub Actions production environment secrets on devsecops-platform (not interviewcoach-AI).
#
# Prerequisites: gh CLI authenticated with devsecops-platform admin access.
# Usage: bash infra/prod/scripts/16-set-github-prod-secrets.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

DEVSECOPS_REPO="${DEVSECOPS_REPO:-moback-ai/devsecops-platform}"

if ! command -v gh >/dev/null 2>&1; then
  echo "Install GitHub CLI: https://cli.github.com/"
  exit 1
fi

ROLE_ARN="${GITHUB_DEPLOY_ROLE_ARN:?Set GITHUB_DEPLOY_ROLE_ARN in prod.env}"
ECR="${ECR_REGISTRY:?Set ECR_REGISTRY in prod.env}"
BUCKET="${STATIC_BUCKET:?Set STATIC_BUCKET in prod.env}"
CF_ID="${CF_DIST_ID:?Set CF_DIST_ID in prod.env}"

gh secret set AWS_DEPLOY_ROLE_ARN --repo "$DEVSECOPS_REPO" --env production --body "$ROLE_ARN"
gh secret set ECR_REGISTRY --repo "$DEVSECOPS_REPO" --env production --body "$ECR"
gh secret set STATIC_S3_BUCKET --repo "$DEVSECOPS_REPO" --env production --body "$BUCKET"
gh secret set CLOUDFRONT_DIST_ID --repo "$DEVSECOPS_REPO" --env production --body "$CF_ID"

echo "GitHub production secrets set on $DEVSECOPS_REPO:"
gh secret list --repo "$DEVSECOPS_REPO" --env production
