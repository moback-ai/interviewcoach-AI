#!/usr/bin/env bash
# Step 7 — Migrate /apps/storage on API host to S3.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

SSH="$(dirname "$0")/ssh-prod.sh"
chmod +x "$SSH"
S3_BUCKET="${S3_BUCKET:-${USER_FILES_BUCKET:?Set USER_FILES_BUCKET in prod.env}}"
LOCAL_PATH="${LOCAL_PATH:-/apps/storage}"

echo "Syncing ${API_HOST}:${LOCAL_PATH} → s3://${S3_BUCKET}/"
"$SSH" "test -d ${LOCAL_PATH} || sudo mkdir -p ${LOCAL_PATH}"

TMP="/tmp/ic-storage-migrate-$$"
mkdir -p "$TMP"
"$SSH" --scp -r "${SSH_USER}@${API_PUBLIC_IP}:${LOCAL_PATH}/" "$TMP/"
aws s3 sync "$TMP/" "s3://${S3_BUCKET}/"
rm -rf "$TMP"

echo "Step 7 complete. Set STORAGE_BACKEND=s3 in Secrets Manager if not already."
