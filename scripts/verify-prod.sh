#!/usr/bin/env bash
# Pre-deploy smoke test for PROD modules (run on laptop only).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"

PYTHON="${ROOT}/backend/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

export LLM_PROVIDER=bedrock
export BEDROCK_CHAT_MODEL=apac.amazon.nova-lite-v1:0
export STT_PRIMARY=openrouter
export STT_FALLBACK=amazon
export JWT_SECRET=local-test-secret-minimum-sixty-four-characters-long-for-jwt
export DB_HOST=127.0.0.1
export DB_PORT=5432
export DB_NAME=interview_db
export DB_USER=interview_user
export DB_PASSWORD=test
export STORAGE_PATH=/tmp/ic-storage
export UPLOAD_FOLDER=/tmp/ic-storage
export AWS_REGION=ap-south-1

"$PYTHON" - <<'PY'
from common.llm.factory import provider_name, get_llm_diagnostics
from common.speech.factory import get_stt_diagnostics

print("LLM provider:", provider_name())
print("STT chain:", get_stt_diagnostics().get("chain"))
assert get_stt_diagnostics().get("chain") == ["openrouter", "amazon"], "prod STT chain mismatch"
print("PROD modules OK")
PY

echo "verify-prod: OK"
