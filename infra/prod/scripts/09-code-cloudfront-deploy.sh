#!/usr/bin/env bash
# Request ACM cert (us-east-1), deploy CloudFront, print DNS cutover targets. PROD only.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
CF_REGION="us-east-1"
# CloudFormation DomainName must be the apex (aliases: apex + www.${apex})
APEX_DOMAIN="${APEX_DOMAIN:-ugaanlabs.ai}"
CANONICAL_HOST="${FRONTEND_DOMAIN:-www.${APEX_DOMAIN}}"
STACK="${CF_STACK_NAME:-interviewcoach-prod-cloudfront}"
TEMPLATE="$(dirname "$0")/../cloudformation/prod-cloudfront.yaml"
STATIC_BUCKET="${STATIC_BUCKET:-ic-static-prod}"
API_ORIGIN="${API_ORIGIN_DOMAIN:-ec2-43-205-215-217.ap-south-1.compute.amazonaws.com}"

CERT_ARN="${ACM_CERT_ARN:-}"
if [[ -z "$CERT_ARN" ]]; then
  EXISTING=$(aws acm list-certificates --region "$CF_REGION" \
    --query "CertificateSummaryList[?DomainName=='${APEX_DOMAIN}'].CertificateArn | [0]" --output text 2>/dev/null || true)
  if [[ -n "$EXISTING" && "$EXISTING" != "None" ]]; then
    CERT_ARN="$EXISTING"
  else
    echo "Requesting ACM certificate for ${APEX_DOMAIN} + www.${APEX_DOMAIN} (us-east-1) ..."
    CERT_ARN=$(aws acm request-certificate \
      --region "$CF_REGION" \
      --domain-name "$APEX_DOMAIN" \
      --subject-alternative-names "www.${APEX_DOMAIN}" \
      --validation-method DNS \
      --query CertificateArn --output text)
  fi
fi

echo "Apex (CF aliases):  ${APEX_DOMAIN}"
echo "Canonical (app URL): https://${CANONICAL_HOST}"
echo "Certificate:         $CERT_ARN"
echo ""
echo "Add these DNS validation CNAMEs at Namecheap (if not already present):"
aws acm describe-certificate --region "$CF_REGION" --certificate-arn "$CERT_ARN" \
  --query 'Certificate.DomainValidationOptions[*].ResourceRecord.{Name:Name,Type:Type,Value:Value}' --output table

STATUS=$(aws acm describe-certificate --region "$CF_REGION" --certificate-arn "$CERT_ARN" \
  --query Certificate.Status --output text)
if [[ "$STATUS" != "ISSUED" ]]; then
  echo ""
  echo "Waiting for certificate validation (up to 10 min) ..."
  for i in $(seq 1 40); do
    STATUS=$(aws acm describe-certificate --region "$CF_REGION" --certificate-arn "$CERT_ARN" \
      --query Certificate.Status --output text)
    [[ "$STATUS" == "ISSUED" ]] && break
    sleep 15
  done
fi

if [[ "$STATUS" != "ISSUED" ]]; then
  echo "Certificate not ISSUED yet ($STATUS). Add validation CNAMEs above, then re-run."
  exit 1
fi

echo "Deploying CloudFront stack $STACK ..."
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK" \
  --template-file "$TEMPLATE" \
  --parameter-overrides \
    DomainName="$APEX_DOMAIN" \
    AcmCertificateArn="$CERT_ARN" \
    StaticBucketName="$STATIC_BUCKET" \
    ApiOriginDomain="$API_ORIGIN" \
  --no-fail-on-empty-changeset

CF_DIST_ID=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue" --output text)
CF_DOMAIN=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionDomainName'].OutputValue" --output text)

echo ""
echo "CloudFront deployed."
echo "  Distribution ID: $CF_DIST_ID"
echo "  Domain:          $CF_DOMAIN"
echo ""
echo "DNS cutover at Namecheap:"
echo "  @   → CNAME/ALIAS → $CF_DOMAIN"
echo "  www → CNAME       → $CF_DOMAIN"
echo ""
echo "Update infra/prod/prod.env:"
echo "  CF_DIST_ID=$CF_DIST_ID"
