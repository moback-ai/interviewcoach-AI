#!/usr/bin/env bash
# Run recommended prod hardening + infra cleanup (interactive-safe defaults).
#
# Before running:
#   - Set ALARM_EMAIL in infra/prod/prod.env
#   - For OpenRouter rotation: OPENROUTER_API_KEY=... (optional, separate step)
#
# Usage: bash infra/prod/scripts/13-prod-hardening-all.sh
set -euo pipefail

SCRIPT_DIR="$(dirname "$0")"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/load-prod-env.sh"

echo "=== 1/6 Security group (close :5000, SSH) ==="
bash "$SCRIPT_DIR/10c-harden-api-security-group.sh"

echo ""
echo "=== 2/6 SNS + CloudWatch alarms ==="
if [[ -n "${ALARM_EMAIL:-}" ]]; then
  bash "$SCRIPT_DIR/11-aws-alarm-sns-topic.sh"
else
  echo "ALARM_EMAIL unset — running alarms without SNS actions."
  bash "$SCRIPT_DIR/12-aws-cloudwatch-alarms.sh"
fi

echo ""
echo "=== 3/6 ACM pending cert cleanup ==="
bash "$SCRIPT_DIR/09d-acm-cleanup-pending.sh"

echo ""
echo "=== 4/6 Legacy storage migration (no-op if empty) ==="
if [[ "${LEGACY_MIGRATION_COMPLETE:-0}" != "1" ]]; then
  bash "$SCRIPT_DIR/07b-migrate-legacy-storage.sh"
else
  echo "LEGACY_MIGRATION_COMPLETE=1 — skip (buckets empty / already migrated)."
fi

echo ""
echo "=== 5/6 CloudFront CloudFormation reconcile ==="
bash "$SCRIPT_DIR/09c-cloudfront-cfn-reconcile.sh"

echo ""
echo "=== 6/6 Secrets sync (DODO_ENV etc. from prod.env) ==="
bash "$SCRIPT_DIR/03c-patch-prod-secret.sh"

echo ""
echo "Hardening batch complete."
echo "Optional: OPENROUTER_API_KEY=sk-or-... bash infra/prod/scripts/03b-rotate-openrouter-key.sh"
echo "Then deploy API if app code changed: bash infra/prod/scripts/06-code-deploy-api.sh"
