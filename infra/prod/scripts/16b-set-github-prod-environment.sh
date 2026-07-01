#!/usr/bin/env bash
# Configure GitHub production environment: required DevSecOps reviewers (second approval layer).
#
# Prerequisites: gh CLI with admin on devsecops-platform.
# Usage: ALLOW_LOCAL_PROD_DEPLOY=1 bash infra/prod/scripts/16b-set-github-prod-environment.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

DEVSECOPS_REPO="${DEVSECOPS_REPO:-moback-ai/devsecops-platform}"
ENV_NAME="${GITHUB_PROD_ENV:-production}"
ACTORS="${DEVSECOPS_GITHUB_ACTORS:-govardhanreddy66,KFKishore23}"

if ! command -v gh >/dev/null 2>&1; then
  echo "Install GitHub CLI: https://cli.github.com/"
  exit 1
fi

reviewers_json="["
first=1
IFS=',' read -ra USERS <<< "$ACTORS"
for u in "${USERS[@]}"; do
  u="${u// /}"
  uid=$(gh api "users/$u" --jq .id)
  if [[ "$first" -eq 1 ]]; then first=0; else reviewers_json+=","; fi
  reviewers_json+="{\"type\":\"User\",\"id\":$uid}"
done
reviewers_json+="]"

if ! gh api -X PUT "repos/$DEVSECOPS_REPO/environments/$ENV_NAME" --input - <<EOF
{
  "reviewers": $reviewers_json,
  "deployment_branch_policy": null,
  "wait_timer": 0,
  "prevent_self_review": false
}
EOF
then
  echo "NOTE: Environment reviewers require GitHub Team/Enterprise. Actor gate (check-devsecops-actor.sh) is the primary control on this plan." >&2
  exit 0
fi

echo "GitHub environment '$ENV_NAME' on $DEVSECOPS_REPO — required reviewers: $ACTORS"
gh api "repos/$DEVSECOPS_REPO/environments/$ENV_NAME" --jq '{reviewers: .reviewers, protection_rules: .protection_rules}'
