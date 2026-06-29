#!/usr/bin/env bash
# Phase 1 (AWS) — Deploy S3 buckets and shared prod stack resources.
# Usage: bash infra/prod/scripts/02-aws-cloudformation.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
STACK_NAME="${STACK_NAME:-interviewcoach-prod-s3}"
TEMPLATE="${TEMPLATE:-$(dirname "$0")/../cloudformation/prod-stack.yaml}"
STATIC_BUCKET="${STATIC_BUCKET:-ic-static-prod}"
USER_FILES_BUCKET="${USER_FILES_BUCKET:-ic-user-files-prod}"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Missing CloudFormation template: $TEMPLATE"
  exit 1
fi

echo "Deploying stack $STACK_NAME in $REGION ..."
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --template-file "$TEMPLATE" \
  --parameter-overrides \
    StaticBucketName="$STATIC_BUCKET" \
    UserFilesBucketName="$USER_FILES_BUCKET" \
  --no-fail-on-empty-changeset

echo "Phase 1 step 2 complete. Buckets: $STATIC_BUCKET, $USER_FILES_BUCKET"
