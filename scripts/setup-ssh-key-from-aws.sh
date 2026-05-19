#!/usr/bin/env bash
# Fetch EC2 deploy key from AWS Secrets Manager into ~/.ssh/interviewcoach-deploy.pem
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
SECRET_ID="${EC2_SSH_SECRET_ID:-interviewcoach/prod/ec2-ssh-key}"
KEY_PATH="${SSH_KEY:-$HOME/.ssh/interviewcoach-deploy.pem}"

mkdir -p "$(dirname "$KEY_PATH")"
chmod 700 "$(dirname "$KEY_PATH")"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ID" \
  --region "$REGION" \
  --query SecretString \
  --output text >"$TMP"

python3 - "$TMP" "$KEY_PATH" <<'PY'
import json
import os
import sys

src, dest = sys.argv[1], sys.argv[2]
raw = open(src, encoding="utf-8").read()
pem = json.loads(raw)["pem"].strip() + "\n"
staging = dest + ".new"
with open(staging, "w", encoding="utf-8") as handle:
    handle.write(pem)
os.chmod(staging, 0o400)
os.replace(staging, dest)
print(f"Wrote {dest} ({len(pem)} bytes)")
PY

echo "Test: ssh -i \"$KEY_PATH\" ubuntu@13.200.28.73 hostname"
