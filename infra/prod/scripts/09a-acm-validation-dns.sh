#!/usr/bin/env bash
# Print ACM DNS validation records for CloudFront (Namecheap). PROD only.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

CF_REGION="us-east-1"
DOMAIN="${FRONTEND_DOMAIN:-ugaanlabs.ai}"
CERT_ARN="${ACM_CERT_ARN:-}"

if [[ -z "$CERT_ARN" ]]; then
  CERT_ARN=$(aws acm list-certificates --region "$CF_REGION" \
    --query "CertificateSummaryList[?DomainName=='${DOMAIN}'].CertificateArn | [0]" --output text)
fi

if [[ -z "$CERT_ARN" || "$CERT_ARN" == "None" ]]; then
  echo "No ACM cert found. Run: bash infra/prod/scripts/09-code-cloudfront-deploy.sh"
  exit 1
fi

echo "Certificate: $CERT_ARN"
aws acm describe-certificate --region "$CF_REGION" --certificate-arn "$CERT_ARN" \
  --query 'Certificate.{Status:Status,Records:DomainValidationOptions[*].ResourceRecord}' --output yaml
