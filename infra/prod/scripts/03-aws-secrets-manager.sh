#!/usr/bin/env bash
# Phase 1 (AWS) — Create or update Secrets Manager JSON (single source of truth for prod config).
# The API reads ONLY this secret at runtime — no .env on prod hosts.
#
# Usage:
#   SECRETS_FILE=backend/secrets.prod.example.json \
#     bash infra/prod/scripts/03-aws-secrets-manager.sh
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
SECRET_ID="${SECRET_ID:-interviewcoach/prod/app}"
SECRETS_FILE="${SECRETS_FILE:-$(dirname "$0")/../../../backend/secrets.prod.example.json}"

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "Missing secrets file: $SECRETS_FILE"
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to validate secrets JSON"
  exit 1
fi

STT_PRIMARY=$(jq -r '.STT_PRIMARY // "amazon"' "$SECRETS_FILE")
REQUIRED_KEYS=(
  LLM_PROVIDER
  BEDROCK_CHAT_MODEL
  STT_PRIMARY
  S3_BUCKET
  REDIS_URL
  DB_HOST
  DB_PASSWORD
  JWT_SECRET
  DODO_PAYMENTS_API_KEY
)
if [[ "$STT_PRIMARY" == *openrouter* ]]; then
  REQUIRED_KEYS+=(OPENROUTER_API_KEY)
fi

for key in "${REQUIRED_KEYS[@]}"; do
  value=$(jq -r --arg k "$key" '.[$k] // empty' "$SECRETS_FILE")
  if [[ -z "$value" || "$value" == "REPLACE_ME" || "$value" == "null" ]]; then
    echo "Fix placeholder for required key: $key"
    exit 1
  fi
done

if ! aws secretsmanager describe-secret --region "$REGION" --secret-id "$SECRET_ID" >/dev/null 2>&1; then
  echo "Creating secret $SECRET_ID in $REGION ..."
  aws secretsmanager create-secret \
    --region "$REGION" \
    --name "$SECRET_ID" \
    --description "InterviewCoach PROD app config (secrets-only)" \
    --secret-string "file://${SECRETS_FILE}"
else
  echo "Updating secret $SECRET_ID in $REGION ..."
  aws secretsmanager put-secret-value \
    --region "$REGION" \
    --secret-id "$SECRET_ID" \
    --secret-string "file://${SECRETS_FILE}"
fi

echo "Phase 1 step 3 complete."
echo "Prod API containers need only:"
echo "  AWS_REGION=$REGION"
echo "  AWS_SECRETS_MANAGER_SECRET_ID=$SECRET_ID"
