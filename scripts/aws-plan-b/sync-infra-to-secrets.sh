#!/usr/bin/env bash
# Merge all EC2/RDS instance IDs and IPs into AWS Secrets Manager (+ optional GitHub)
#
# Usage:
#   ./sync-infra-to-secrets.sh --apply
#   ./sync-infra-to-secrets.sh --apply --github
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.env"
[[ -f "${SCRIPT_DIR}/outputs.env" ]] && source "${SCRIPT_DIR}/outputs.env"

SECRET_ID="${AWS_SECRETS_MANAGER_SECRET_ID:-interviewcoach/prod/app}"
APPLY=0
GITHUB=0
for arg in "$@"; do
  [[ "$arg" == "--apply" ]] && APPLY=1
  [[ "$arg" == "--github" ]] && GITHUB=1
done

TMP="$(mktemp)"
aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$SECRET_ID" \
  --query SecretString --output text >"$TMP"

export TMP SECRET_ID
export FRONTEND_INSTANCE_ID FRONTEND_PUBLIC_IP FRONTEND_PRIVATE_IP
export API_INSTANCE_ID API_PUBLIC_IP API_PRIVATE_IP
export AI_INSTANCE_ID AI_PUBLIC_IP AI_PRIVATE_IP
export RDS_INSTANCE_ID AWS_REGION OLLAMA_HOST OLLAMA_HEALTH_URL

python3 <<'PY'
import json, os

path = os.environ["TMP"]
with open(path) as f:
    data = json.load(f)

updates = {
    "FRONTEND_INSTANCE_ID": os.environ["FRONTEND_INSTANCE_ID"],
    "FRONTEND_HOST": os.environ["FRONTEND_PUBLIC_IP"],
    "FRONTEND_PUBLIC_IP": os.environ["FRONTEND_PUBLIC_IP"],
    "FRONTEND_PRIVATE_IP": os.environ["FRONTEND_PRIVATE_IP"],
    "API_INSTANCE_ID": os.environ.get("API_INSTANCE_ID", ""),
    "API_PUBLIC_IP": os.environ.get("API_PUBLIC_IP", ""),
    "API_PRIVATE_IP": os.environ.get("API_PRIVATE_IP", ""),
    "BACKEND_HOST": os.environ.get("API_PUBLIC_IP", os.environ.get("AI_PUBLIC_IP", "")),
    "AI_INSTANCE_ID": os.environ["AI_INSTANCE_ID"],
    "AI_PUBLIC_IP": os.environ["AI_PUBLIC_IP"],
    "AI_HOST": os.environ["AI_PUBLIC_IP"],
    "AI_PRIVATE_IP": os.environ["AI_PRIVATE_IP"],
    "OLLAMA_HOST": os.environ.get("OLLAMA_HOST", f"http://{os.environ['AI_PRIVATE_IP']}:11434"),
    "OLLAMA_HEALTH_URL": os.environ.get(
        "OLLAMA_HEALTH_URL", f"http://{os.environ['AI_PRIVATE_IP']}:11434/api/tags"
    ),
    "RDS_INSTANCE_ID": os.environ["RDS_INSTANCE_ID"],
    "AWS_REGION": os.environ["AWS_REGION"],
    "INFRA_LAYOUT": "split-api",
    "INFRA_UPDATED_AT": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "TRANSCRIBE_SERVICE_URL": f"http://{os.environ['AI_PRIVATE_IP']}:5001",
    "INTERVIEW_FAST_WRAPUP": "true",
    "INTERVIEW_SERVER_TTS": "false",
    "INTERVIEW_MAX_CONCURRENT": "12",
    "INTERVIEW_QUEUE_WAIT_SECONDS": "90",
    "INTERVIEW_RESPONSE_TIMEOUT_SECONDS": "90",
    "OLLAMA_MODEL": os.environ.get("OLLAMA_MODEL", "llama3.2:3b"),
    "OLLAMA_NUM_PREDICT": "384",
    "ENFORCE_SERVICE_HOURS": "true",
    "SERVICE_HOURS_TZ": "Asia/Kolkata",
    "SERVICE_HOURS_START": "10:00",
    "SERVICE_HOURS_END": "20:00",
}
data.update({k: v for k, v in updates.items() if v})
with open(path, "w") as f:
    json.dump(data, f)

print("Keys added/updated:")
for k in sorted(updates):
    print(f"  {k}={updates[k]}")
PY

if [[ "$APPLY" -eq 1 ]]; then
  aws secretsmanager put-secret-value --region "$AWS_REGION" \
    --secret-id "$SECRET_ID" --secret-string "file://${TMP}"
  echo "AWS Secrets Manager updated: $SECRET_ID"
else
  echo "DRY-RUN: would put-secret-value"
fi

if [[ "$GITHUB" -eq 1 && "$APPLY" -eq 1 ]]; then
  "${SCRIPT_DIR}/sync-github-secrets.sh" --apply
fi

rm -f "$TMP"
