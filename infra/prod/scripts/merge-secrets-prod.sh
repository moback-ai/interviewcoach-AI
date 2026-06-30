#!/usr/bin/env bash
# Merge prod template with current Secrets Manager JSON (keeps legacy keys for rollback).
# Usage:
#   OPENROUTER_API_KEY=sk-or-... bash infra/prod/scripts/merge-secrets-prod.sh
# Output: backend/secrets.prod.json (gitignored)
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
SECRET_ID="${SECRET_ID:-interviewcoach/prod/app}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
TEMPLATE="${TEMPLATE:-$ROOT/backend/secrets.prod.example.json}"
OUT="${OUT:-$ROOT/backend/secrets.prod.json}"
CURRENT="$(mktemp)"
trap 'rm -f "$CURRENT"' EXIT

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Missing template: $TEMPLATE"
  exit 1
fi

aws secretsmanager get-secret-value \
  --region "$REGION" \
  --secret-id "$SECRET_ID" \
  --query SecretString \
  --output text > "$CURRENT"

python3 - "$TEMPLATE" "$CURRENT" "$OUT" <<'PY'
import json
import os
import sys

template_path, current_path, out_path = sys.argv[1:4]
template = json.load(open(template_path))
current = json.load(open(current_path))

def empty(v):
    if v is None:
        return True
    s = str(v).strip()
    return not s or s in ("REPLACE_ME", "null") or "REPLACE_" in s

merged = dict(template)
for key, value in current.items():
    if not empty(value):
        merged[key] = value

# PROD overrides from prod.env / environment
overrides = {}
for key in (
    "S3_BUCKET", "STT_S3_BUCKET", "STATIC_BUCKET", "S3_BUCKET_PRIMARY", "S3_BUCKET_SECONDARY",
    "S3_REGION", "DOMAIN", "BACKEND_API_BASE", "PUBLIC_STORAGE_URL", "FRONTEND_DOMAIN",
    "BEDROCK_REGION", "BEDROCK_CHAT_MODEL", "BEDROCK_REPORT_MODEL", "REDIS_URL", "DODO_ENV",
    "DB_HOST", "DB_NAME", "DB_USER", "RDS_INSTANCE_ID", "STT_PRIMARY", "STT_FALLBACK",
):
    val = os.environ.get(key, "").strip()
    if val:
        overrides[key] = val

user_files = os.environ.get("USER_FILES_BUCKET", os.environ.get("S3_BUCKET", "")).strip()
if user_files:
    overrides["S3_BUCKET"] = user_files
    overrides["STT_S3_BUCKET"] = user_files

for key, value in overrides.items():
    merged[key] = value

# Never drop live OpenRouter key when STT uses OpenRouter
stt_primary = (merged.get("STT_PRIMARY") or "amazon").lower()
if "openrouter" in stt_primary and empty(merged.get("OPENROUTER_API_KEY")):
    live_key = current.get("OPENROUTER_API_KEY")
    if not empty(live_key):
        merged["OPENROUTER_API_KEY"] = live_key

# PROD overrides (prod DB endpoint from live RDS if still placeholder)
if empty(merged.get("DB_HOST")) and not empty(current.get("DB_HOST")):
    merged["DB_HOST"] = current["DB_HOST"]

# Redis: sidecar on API host (see docker/compose.prod.yml)
merged["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://redis:6379/0")

or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
stt_primary = overrides.get("STT_PRIMARY") or merged.get("STT_PRIMARY") or "amazon"
if or_key:
    merged["OPENROUTER_API_KEY"] = or_key
elif "openrouter" in stt_primary.lower() and empty(merged.get("OPENROUTER_API_KEY")):
    print("ERROR: OPENROUTER_API_KEY is required when STT_PRIMARY includes openrouter.", file=sys.stderr)
    sys.exit(1)
else:
    merged.pop("OPENROUTER_API_KEY", None)

with open(out_path, "w") as f:
    json.dump(merged, f, indent=2, sort_keys=True)
    f.write("\n")

required = [
    "LLM_PROVIDER", "BEDROCK_CHAT_MODEL", "STT_PRIMARY",
    "S3_BUCKET", "REDIS_URL", "DB_HOST", "DB_PASSWORD", "JWT_SECRET",
    "DODO_PAYMENTS_API_KEY",
]
if "openrouter" in (merged.get("STT_PRIMARY") or "").lower():
    required.append("OPENROUTER_API_KEY")
missing = [k for k in required if empty(merged.get(k))]
legacy_only = sorted(k for k in current if k not in template)
print(f"Wrote {out_path}")
print(f"Total keys: {len(merged)} (legacy preserved: {len(legacy_only)})")
if missing:
    print("Still missing:", ", ".join(missing))
    sys.exit(1)
print("Merge OK — ready for 03-aws-secrets-manager.sh")
PY
