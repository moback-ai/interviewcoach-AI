#!/usr/bin/env bash
# Patch non-secret prod.env fields into live Secrets Manager JSON (no key rotation).
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
SECRET_ID="${SECRET_ID:-interviewcoach/prod/app}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

aws secretsmanager get-secret-value --region "$REGION" --secret-id "$SECRET_ID" \
  --query SecretString --output text > "$TMP"

python3 - "$TMP" <<'PY'
import json
import os
import sys

path = sys.argv[1]
data = json.load(open(path))

patch_keys = (
    "DODO_ENV", "DOMAIN", "BACKEND_API_BASE", "PUBLIC_STORAGE_URL", "FRONTEND_DOMAIN",
    "S3_BUCKET", "STT_S3_BUCKET", "STT_PRIMARY", "STT_FALLBACK", "REDIS_URL",
    "BEDROCK_REGION", "BEDROCK_CHAT_MODEL", "BEDROCK_REPORT_MODEL",
)
for key in patch_keys:
    val = os.environ.get(key, "").strip()
    if val:
        data[key] = val

user_files = os.environ.get("USER_FILES_BUCKET", os.environ.get("S3_BUCKET", "")).strip()
if user_files:
    data["S3_BUCKET"] = user_files
    data["STT_S3_BUCKET"] = user_files

with open(path, "w") as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.write("\n")
print("Patched keys:", ", ".join(k for k in patch_keys if os.environ.get(k, "").strip()))
PY

aws secretsmanager put-secret-value --region "$REGION" --secret-id "$SECRET_ID" --secret-string "file://${TMP}"
echo "Secret $SECRET_ID patched (DODO_ENV=${DODO_ENV:-unset}). Restart API to apply."
