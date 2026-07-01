#!/usr/bin/env bash
# Migrate legacy Plan B S3 buckets + EC2 /apps/storage → ic-user-files-prod.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
DEST="${S3_BUCKET:-${USER_FILES_BUCKET:-ic-user-files-prod}}"
PRIMARY="${S3_BUCKET_PRIMARY:-interviewcoach-storage-1776239119}"
SECONDARY="${S3_BUCKET_SECONDARY:-interviewcoach-storage-1776239227}"

echo "=== Legacy bucket → s3://${DEST} ==="
for src in "$PRIMARY" "$SECONDARY"; do
  if aws s3api head-bucket --bucket "$src" --region "$REGION" 2>/dev/null; then
    echo "Syncing s3://${src}/ → s3://${DEST}/legacy/${src}/"
    aws s3 sync "s3://${src}/" "s3://${DEST}/legacy/${src}/" --region "$REGION"
  else
    echo "Skip missing bucket: $src"
  fi
done

echo "=== EC2 ${LOCAL_PATH:-/apps/storage} → s3://${DEST} ==="
bash "$(dirname "$0")/07-code-migrate-storage.sh"

echo "Storage migration complete."
