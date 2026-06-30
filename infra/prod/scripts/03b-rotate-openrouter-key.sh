#!/usr/bin/env bash
# Rotate OpenRouter API key in Secrets Manager (merge keeps all other live secrets).
#
# Usage:
#   OPENROUTER_API_KEY=sk-or-v1-... bash infra/prod/scripts/03b-rotate-openrouter-key.sh
#   bash infra/prod/scripts/06-code-deploy-api.sh   # restart API to pick up secret
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "Provide a new key: OPENROUTER_API_KEY=sk-or-v1-... $0"
  echo "Revoke the old key at https://openrouter.ai/keys after deploy."
  exit 1
fi

SCRIPT_DIR="$(dirname "$0")"
export OPENROUTER_API_KEY

bash "$SCRIPT_DIR/merge-secrets-prod.sh"
SECRETS_FILE="$SCRIPT_DIR/../../../backend/secrets.prod.json" bash "$SCRIPT_DIR/03-aws-secrets-manager.sh"

echo ""
echo "OpenRouter key updated in Secrets Manager."
echo "Restart API: bash infra/prod/scripts/06-code-deploy-api.sh"
