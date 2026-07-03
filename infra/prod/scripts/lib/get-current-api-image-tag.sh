#!/usr/bin/env bash
# Print the interviewcoach-api image tag from the prod ASG launch template UserData.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REGION="${AWS_REGION:-ap-south-1}"
ASG="${ASG_NAME:-interviewcoach-prod-api-asg}"

LT_ID=$(aws autoscaling describe-auto-scaling-groups \
  --region "$REGION" \
  --auto-scaling-group-names "$ASG" \
  --query 'AutoScalingGroups[0].LaunchTemplate.LaunchTemplateId' \
  --output text)
[[ -n "$LT_ID" && "$LT_ID" != "None" ]] || { echo "No launch template for ASG $ASG" >&2; exit 1; }

USER_DATA=$(aws ec2 describe-launch-template-versions \
  --region "$REGION" \
  --launch-template-id "$LT_ID" \
  --versions '$Latest' \
  --query 'LaunchTemplateVersions[0].LaunchTemplateData.UserData' \
  --output text)

python3 - "$USER_DATA" <<'PY'
import base64
import re
import sys

raw = sys.argv[1]
decoded = base64.b64decode(raw).decode()
match = re.search(r"interviewcoach-api:([^\s]+)", decoded)
if not match:
    raise SystemExit("Could not find interviewcoach-api image tag in launch template UserData")
print(match.group(1))
PY
