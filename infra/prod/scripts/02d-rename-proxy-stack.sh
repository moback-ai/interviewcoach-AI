#!/usr/bin/env bash
# Rename CFN stack interviewcoach-prod-rds-proxy → interviewcoach-prod-proxy (retain + import).
#
# Usage: CONFIRM=YES bash infra/prod/scripts/02d-rename-proxy-stack.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REGION="${AWS_REGION:-ap-south-1}"
OLD_STACK="${OLD_PROXY_STACK_NAME:-interviewcoach-prod-rds-proxy}"
NEW_STACK="${PROXY_STACK_NAME:-interviewcoach-prod-proxy}"
TEMPLATE="$(dirname "$0")/../cloudformation/prod-rds-proxy.yaml"
IMPORT_JSON="$(mktemp)"
PARAM_FILE="$(mktemp)"
IMPORT_PARAMS_JSON="$(mktemp)"
RESOURCES_FILE="$(mktemp)"
RETAIN_TEMPLATE="$(mktemp)"
IMPORT_TEMPLATE="$(mktemp)"
trap 'rm -f "$IMPORT_JSON" "$PARAM_FILE" "$IMPORT_PARAMS_JSON" "$RESOURCES_FILE" "$RETAIN_TEMPLATE" "$IMPORT_TEMPLATE"' EXIT

if [[ "${CONFIRM:-}" != "YES" ]]; then
  echo "Renames $OLD_STACK → $NEW_STACK (retain resources, import into new stack)."
  echo "Re-run: CONFIRM=YES bash $0"
  exit 1
fi

if aws cloudformation describe-stacks --region "$REGION" --stack-name "$NEW_STACK" >/dev/null 2>&1; then
  echo "Stack $NEW_STACK already exists — nothing to rename."
  exit 0
fi

if ! aws cloudformation describe-stacks --region "$REGION" --stack-name "$OLD_STACK" >/dev/null 2>&1; then
  if aws cloudformation describe-stacks --region "$REGION" --stack-name "$NEW_STACK" >/dev/null 2>&1; then
    STATUS=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$NEW_STACK" \
      --query 'Stacks[0].StackStatus' --output text)
    if [[ "$STATUS" == "REVIEW_IN_PROGRESS" ]]; then
      aws cloudformation delete-stack --region "$REGION" --stack-name "$NEW_STACK"
      aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$NEW_STACK"
    elif [[ "$STATUS" == "CREATE_COMPLETE" || "$STATUS" == "UPDATE_COMPLETE" ]]; then
      echo "Stack $NEW_STACK already exists — nothing to rename."
      exit 0
    fi
  fi
  echo "Resume: $OLD_STACK deleted — importing into $NEW_STACK ..."
  python3 "${SCRIPT_DIR}/lib/build-proxy-import-json.py" "$REGION" "$RDS_SECURITY_GROUP_ID" "interviewcoach-prod-proxy" \
    > "$IMPORT_JSON"
  write_params_from_prod_env() {
    python3 - "$PARAM_FILE" <<PY
import json, os
params = [
    ("VpcId", os.environ["VPC_ID"]),
    ("SubnetIds", os.environ.get("PROXY_SUBNET_IDS", os.environ["PUBLIC_SUBNET_IDS"])),
    ("DbInstanceIdentifier", os.environ.get("RDS_INSTANCE_ID", "interviewcoach-db")),
    ("DbSecretArn", os.environ.get("RDS_PROXY_SECRET_ARN", "")),
    ("ApiSecurityGroupId", os.environ["API_ASG_SG_ID"]),
    ("RdsSecurityGroupId", os.environ["RDS_SECURITY_GROUP_ID"]),
]
open("$PARAM_FILE", "w").write(json.dumps(
    [{"ParameterKey": k, "ParameterValue": v} for k, v in params if v]
))
PY
  }
  SECRET_ARN=$(aws secretsmanager describe-secret --region "$REGION" \
    --secret-id "${RDS_PROXY_SECRET_ID:-interviewcoach/prod/rds-proxy}" \
    --query ARN --output text 2>/dev/null || true)
  export RDS_PROXY_SECRET_ARN="$SECRET_ARN"
  write_params_from_prod_env
  python3 "$(dirname "$0")/lib/add-cfn-retain.py" "$TEMPLATE" "$RETAIN_TEMPLATE"
  python3 "$(dirname "$0")/lib/cfn-import-params-file.py" "$PARAM_FILE" "$IMPORT_PARAMS_JSON"
  python3 - <<'PY' "$RETAIN_TEMPLATE" "$IMPORT_TEMPLATE"
import pathlib, sys
src, dst = sys.argv[1:3]
out, skip = [], False
for line in pathlib.Path(src).read_text(encoding="utf-8").splitlines():
    if line.rstrip() == "Outputs:":
        skip = True
        continue
    if skip:
        continue
    out.append(line)
pathlib.Path(dst).write_text("\n".join(out) + "\n")
PY
  CHANGE_SET="import-${NEW_STACK}-$(date +%s)"
  aws cloudformation create-change-set \
    --region "$REGION" \
    --stack-name "$NEW_STACK" \
    --change-set-name "$CHANGE_SET" \
    --change-set-type IMPORT \
    --resources-to-import "file://${IMPORT_JSON}" \
    --template-body "file://${IMPORT_TEMPLATE}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters "file://${IMPORT_PARAMS_JSON}"
  aws cloudformation wait change-set-create-complete \
    --region "$REGION" --stack-name "$NEW_STACK" --change-set-name "$CHANGE_SET"
  aws cloudformation execute-change-set \
    --region "$REGION" --stack-name "$NEW_STACK" --change-set-name "$CHANGE_SET"
  aws cloudformation wait stack-import-complete --region "$REGION" --stack-name "$NEW_STACK"
  PARAM_OVERRIDES=()
  while IFS= read -r line; do PARAM_OVERRIDES+=("$line"); done \
    < <(python3 "$(dirname "$0")/lib/cfn-format-params.py" deploy "$PARAM_FILE")
  aws cloudformation deploy \
    --region "$REGION" \
    --stack-name "$NEW_STACK" \
    --template-file "$TEMPLATE" \
    --parameter-overrides "${PARAM_OVERRIDES[@]}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset
  echo "Renamed $OLD_STACK → $NEW_STACK"
  exit 0
fi

aws cloudformation describe-stacks --region "$REGION" --stack-name "$OLD_STACK" \
  --query 'Stacks[0].Parameters' --output json > "$PARAM_FILE"

aws cloudformation list-stack-resources --region "$REGION" --stack-name "$OLD_STACK" --output json \
  > "$RESOURCES_FILE"

python3 - "$REGION" "$IMPORT_JSON" "$RESOURCES_FILE" <<'PY'
import json, pathlib, subprocess, sys

region, import_path, resources_path = sys.argv[1:4]
rows = json.loads(pathlib.Path(resources_path).read_text())["StackResourceSummaries"]

def ingress_identifier(rule_id: str) -> dict:
    rule = json.loads(subprocess.check_output([
        "aws", "ec2", "describe-security-group-rules",
        "--region", region,
        "--security-group-rule-ids", rule_id,
        "--query", "SecurityGroupRules[0]",
        "--output", "json",
    ], text=True))
    ident = {
        "GroupId": rule["GroupId"],
        "IpProtocol": rule["IpProtocol"],
        "FromPort": str(rule["FromPort"]),
        "ToPort": str(rule["ToPort"]),
    }
    ref = rule.get("ReferencedGroupInfo") or {}
    if ref.get("GroupId"):
        ident["SourceSecurityGroupId"] = ref["GroupId"]
    elif rule.get("CidrIpv4"):
        ident["CidrIp"] = rule["CidrIpv4"]
    return ident

def identifier(row):
    rtype, lid, pid = row["ResourceType"], row["LogicalResourceId"], row["PhysicalResourceId"]
    if rtype == "AWS::IAM::Role":
        return {"RoleName": pid}
    if rtype == "AWS::EC2::SecurityGroup":
        return {"Id": pid}
    if rtype == "AWS::EC2::SecurityGroupIngress":
        return {"Id": pid}
    if rtype == "AWS::RDS::DBProxy":
        return {"DBProxyName": pid}
    if rtype == "AWS::RDS::DBProxyTargetGroup":
        tg = json.loads(subprocess.check_output([
            "aws", "rds", "describe-db-proxy-target-groups",
            "--region", region,
            "--target-group-arn", pid,
            "--query", "TargetGroups[0]",
            "--output", "json",
        ], text=True))
        return {
            "DBProxyName": tg["DBProxyName"],
            "TargetGroupName": tg["TargetGroupName"],
        }
    raise SystemExit(f"Unsupported import type {rtype} ({lid})")

imports = []
for row in rows:
    imports.append({
        "ResourceType": row["ResourceType"],
        "LogicalResourceId": row["LogicalResourceId"],
        "ResourceIdentifier": identifier(row),
    })

pathlib.Path(import_path).write_text(json.dumps(imports, indent=2))
print(f"Built {len(imports)} resources for import.")
PY

python3 "$(dirname "$0")/lib/add-cfn-retain.py" "$TEMPLATE" "$RETAIN_TEMPLATE"

PARAM_OVERRIDES=()
while IFS= read -r line; do
  PARAM_OVERRIDES+=("$line")
done < <(python3 "$(dirname "$0")/lib/cfn-format-params.py" deploy "$PARAM_FILE")

echo "Updating $OLD_STACK with Retain policies ..."
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$OLD_STACK" \
  --template-file "$RETAIN_TEMPLATE" \
  --parameter-overrides "${PARAM_OVERRIDES[@]}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset

echo "Deleting $OLD_STACK (resources retained via DeletionPolicy) ..."
aws cloudformation delete-stack --region "$REGION" --stack-name "$OLD_STACK"
aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$OLD_STACK"

python3 "$(dirname "$0")/lib/cfn-import-params-file.py" "$PARAM_FILE" "$IMPORT_PARAMS_JSON"

python3 - <<'PY' "$RETAIN_TEMPLATE" "$IMPORT_TEMPLATE"
import pathlib, sys
src, dst = sys.argv[1:3]
out, skip = [], False
for line in pathlib.Path(src).read_text(encoding="utf-8").splitlines():
    if line.rstrip() == "Outputs:":
        skip = True
        continue
    if skip:
        continue
    out.append(line)
pathlib.Path(dst).write_text("\n".join(out) + "\n")
PY

CHANGE_SET="import-${NEW_STACK}-$(date +%s)"
aws cloudformation create-change-set \
  --region "$REGION" \
  --stack-name "$NEW_STACK" \
  --change-set-name "$CHANGE_SET" \
  --change-set-type IMPORT \
  --resources-to-import "file://${IMPORT_JSON}" \
  --template-body "file://${IMPORT_TEMPLATE}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameters "file://${IMPORT_PARAMS_JSON}"

aws cloudformation wait change-set-create-complete \
  --region "$REGION" --stack-name "$NEW_STACK" --change-set-name "$CHANGE_SET"

aws cloudformation execute-change-set \
  --region "$REGION" --stack-name "$NEW_STACK" --change-set-name "$CHANGE_SET"

aws cloudformation wait stack-import-complete --region "$REGION" --stack-name "$NEW_STACK"

aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$NEW_STACK" \
  --template-file "$TEMPLATE" \
  --parameter-overrides "${PARAM_OVERRIDES[@]}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset

echo "Renamed $OLD_STACK → $NEW_STACK"
