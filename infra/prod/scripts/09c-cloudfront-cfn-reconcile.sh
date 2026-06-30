#!/usr/bin/env bash
# Reconcile CloudFront CloudFormation stack with live distribution (fixes UPDATE_ROLLBACK drift).
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
STACK="${CF_STACK_NAME:-interviewcoach-prod-cloudfront}"
TEMPLATE="$(dirname "$0")/../cloudformation/prod-cloudfront.yaml"
APEX_DOMAIN="${APEX_DOMAIN:-ugaanlabs.ai}"
STATIC_BUCKET="${STATIC_BUCKET:-ic-static-prod}"
STATIC_REGION="${S3_REGION:-ap-south-1}"
API_ORIGIN="${API_ORIGIN_DOMAIN:?Set API_ORIGIN_DOMAIN}"
CERT_ARN="${ACM_CERT_ARN:?Set ACM_CERT_ARN to issued cert}"
LIVE_DIST="${CF_DIST_ID:?Set CF_DIST_ID}"

STATUS=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "$STATUS" == *"ROLLBACK"* ]]; then
  echo "Stack $STATUS — continuing rollback if needed ..."
  aws cloudformation continue-update-rollback --region "$REGION" --stack-name "$STACK" 2>/dev/null || true
  for i in $(seq 1 30); do
    STATUS=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
      --query 'Stacks[0].StackStatus' --output text)
    [[ "$STATUS" != *"IN_PROGRESS"* ]] && break
    sleep 10
  done
fi

echo "Deploying CloudFront stack (cert + apex redirect + API origin policy) ..."
if aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK" \
  --template-file "$TEMPLATE" \
  --parameter-overrides \
    DomainName="$APEX_DOMAIN" \
    AcmCertificateArn="$CERT_ARN" \
    StaticBucketName="$STATIC_BUCKET" \
    StaticBucketRegion="$STATIC_REGION" \
    ApiOriginDomain="$API_ORIGIN" \
  --no-fail-on-empty-changeset; then
  STACK_DIST=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue" --output text 2>/dev/null || true)
  if [[ -n "$STACK_DIST" && "$STACK_DIST" != "None" && "$STACK_DIST" != "$LIVE_DIST" ]]; then
    echo "WARN: stack distribution $STACK_DIST != live $LIVE_DIST — verify DNS manually."
  else
    echo "CloudFormation reconciled with live distribution $LIVE_DIST"
  fi
else
  echo "CloudFormation deploy failed. Live CloudFront ($LIVE_DIST) is unchanged."
  exit 1
fi
