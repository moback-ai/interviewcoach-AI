#!/usr/bin/env bash
# CloudFront DNS cutover at Namecheap (after 09-code-cloudfront-deploy.sh succeeds).
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
STACK="${CF_STACK_NAME:-interviewcoach-prod-cloudfront}"
DOMAIN="${FRONTEND_DOMAIN:-ugaanlabs.ai}"

CF_DOMAIN=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionDomainName'].OutputValue" --output text 2>/dev/null || true)

if [[ -z "$CF_DOMAIN" || "$CF_DOMAIN" == "None" ]]; then
  echo "CloudFront stack not deployed. Run 09-code-cloudfront-deploy.sh first."
  exit 1
fi

echo "=== CloudFront cutover (Namecheap) ==="
echo ""
echo "1. Remove A record @ → EC2 IP (if present)"
echo "2. Add ALIAS/CNAME records:"
echo "   @   → $CF_DOMAIN  (Namecheap ALIAS or CNAME flattening)"
echo "   www → $CF_DOMAIN"
echo ""
echo "3. Verify:"
echo "   curl -fsS https://${DOMAIN}/api/health"
echo ""
read -r -p "Type YES when DNS updated: " CONFIRM
[[ "$CONFIRM" == "YES" ]] || exit 1
curl -fsS "https://${DOMAIN}/api/health" | head -c 300
echo ""
echo "Cutover complete."
