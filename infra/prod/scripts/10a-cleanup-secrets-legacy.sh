#!/usr/bin/env bash
# Remove Plan B legacy keys from Secrets Manager (safe after Bedrock/STT cutover).
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
SECRET_ID="${SECRET_ID:-interviewcoach/prod/app}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

aws secretsmanager get-secret-value \
  --region "$REGION" \
  --secret-id "$SECRET_ID" \
  --query SecretString \
  --output text > "$TMP"

python3 - "$TMP" <<'PY'
import json
import sys

path = sys.argv[1]
data = json.load(open(path))

LEGACY_PREFIXES = ("OLLAMA_", "WHISPER_")
LEGACY_EXACT = {
    "TRANSCRIBE_SERVICE_URL",
    "TRANSCRIBE_INTERNAL_TOKEN",
    "ENABLE_AI_WARMUP",
    "JD_PARSE_USE_OLLAMA",
    "QUESTION_GEN_USE_OLLAMA",
    "QUESTION_GEN_OLLAMA_TIMEOUT_SECONDS",
    "JD_PARSE_OLLAMA_TIMEOUT_SECONDS",
}

removed = []
for key in list(data):
    if key in LEGACY_EXACT or key.startswith(LEGACY_PREFIXES):
        removed.append(key)
        del data[key]

with open(path, "w") as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.write("\n")

print(f"Removed {len(removed)} legacy keys:")
for k in sorted(removed):
    print(f"  - {k}")
PY

aws secretsmanager put-secret-value \
  --region "$REGION" \
  --secret-id "$SECRET_ID" \
  --secret-string "file://${TMP}"

echo "Secrets cleanup complete."
