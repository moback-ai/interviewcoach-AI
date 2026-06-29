#!/usr/bin/env bash
# Fetch current Secrets Manager JSON and save a local rollback copy (never commit).
# Usage: bash infra/prod/scripts/00-backup-secrets.sh
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
SECRET_ID="${SECRET_ID:-interviewcoach/prod/app}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backend/.secrets-backup}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/plan-b-${STAMP}.json"

mkdir -p "$BACKUP_DIR"
aws secretsmanager get-secret-value \
  --region "$REGION" \
  --secret-id "$SECRET_ID" \
  --query SecretString \
  --output text > "$OUT"

ln -sf "$(basename "$OUT")" "$BACKUP_DIR/plan-b-latest.json"
echo "Saved rollback copy: $OUT"
echo "Symlink: $BACKUP_DIR/plan-b-latest.json"
