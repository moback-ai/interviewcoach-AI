#!/usr/bin/env bash
# Enable versioning on the prod static bucket for fast frontend rollback.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
BUCKET="${STATIC_BUCKET:-ic-static-prod}"

echo "Enabling versioning on s3://${BUCKET} ..."
aws s3api put-bucket-versioning \
  --region "$REGION" \
  --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled

echo "Versioning enabled. Roll back frontend by restoring a previous object version in S3."
