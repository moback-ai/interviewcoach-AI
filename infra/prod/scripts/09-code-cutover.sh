#!/usr/bin/env bash
# Step 7 — CloudFront / DNS cutover (manual confirmation required).
set -euo pipefail

echo "=== Step 7: Cutover ==="
echo "1. CloudFront origin /api/* → new ALB or API host"
echo "2. CloudFront origin default → S3 static bucket"
echo "3. Route53 A/AAAA alias → CloudFront distribution"
echo "4. Verify: curl -fsS https://ugaanlabs.ai/api/health"
echo ""
read -r -p "Type YES to confirm cutover completed: " CONFIRM
if [[ "$CONFIRM" != "YES" ]]; then
  echo "Aborted."
  exit 1
fi
echo "Step 7 marked complete."
