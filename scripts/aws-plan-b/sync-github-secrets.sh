#!/usr/bin/env bash
# Sync deploy-related keys from AWS Secrets Manager -> GitHub repo secrets
#
# Usage:
#   ./sync-github-secrets.sh           # dry-run
#   ./sync-github-secrets.sh --apply
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.env"

SECRET_ID="${AWS_SECRETS_MANAGER_SECRET_ID:-interviewcoach/prod/app}"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

# Keys used by .github/workflows/deploy.yml from GitHub secrets
GITHUB_KEYS=(
  BACKEND_HOST
  FRONTEND_HOST
  DB_HOST
  DB_PORT
  DB_NAME
  DB_USER
  DB_PASSWORD
  JWT_SECRET
  VITE_API_BASE_URL
  VITE_STORAGE_URL
)

payload="$(aws secretsmanager get-secret-value \
  --region "$AWS_REGION" \
  --secret-id "$SECRET_ID" \
  --query SecretString --output text)"

echo "Source: AWS Secrets Manager / ${SECRET_ID}"
echo ""

for key in "${GITHUB_KEYS[@]}"; do
  value="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('$key',''))" <<<"$payload")"
  if [[ -z "$value" ]]; then
    echo "SKIP $key (not in AWS secret)"
    continue
  fi
  if [[ "$APPLY" -eq 1 ]]; then
    gh secret set "$key" --body "$value"
    echo "SET  $key"
  else
    echo "DRY  $key -> (${#value} chars)"
  fi
done

echo ""
echo "Not synced via this script (unchanged / manual only):"
echo "  EC2_SSH_KEY  — stays in GitHub; same key must exist on all EC2 instances"
echo "  EC2_USER     — typically ubuntu"
echo ""
echo "Runtime-only keys (AWS secret only, not GitHub): OLLAMA_HOST, Plan B flags, SMTP, S3, etc."
