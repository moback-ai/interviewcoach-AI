#!/usr/bin/env bash
# Run recommended prod hardening + infra cleanup (interactive-safe defaults).
#
# Before running:
#   - Set ALARM_EMAIL in infra/prod/prod.env
#   - OpenRouter key: add later via 03b-rotate-openrouter-key.sh
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
echo "=== 4/6 Legacy storage migration (optional; Plan B buckets kept) ==="
if [[ "${SKIP_LEGACY_MIGRATION:-0}" == "1" ]]; then
  echo "SKIP_LEGACY_MIGRATION=1 — skipped."
else
  bash "$SCRIPT_DIR/07b-migrate-legacy-storage.sh" || echo "Migration skipped or no legacy data."
fi

echo ""
echo "=== 5/6 CloudFront CloudFormation reconcile ==="
bash "$SCRIPT_DIR/09c-cloudfront-cfn-reconcile.sh"

echo ""
echo "=== 6/6 Secrets sync (DODO_ENV=test from prod.env) ==="
bash "$SCRIPT_DIR/03c-patch-prod-secret.sh"

echo ""
echo "Hardening batch complete."
echo "OpenRouter: add key later — OPENROUTER_API_KEY=sk-or-... bash infra/prod/scripts/03b-rotate-openrouter-key.sh"
echo "Deploy API if needed: bash infra/prod/scripts/06-code-deploy-api.sh"
