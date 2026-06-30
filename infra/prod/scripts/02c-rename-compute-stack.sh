#!/usr/bin/env bash
# Rename CFN stack interviewcoach-prod-hybrid → interviewcoach-prod-compute (retain + import).
#
# Usage: CONFIRM=YES bash infra/prod/scripts/02c-rename-compute-stack.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REGION="${AWS_REGION:-ap-south-1}"
OLD_STACK="${OLD_COMPUTE_STACK_NAME:-interviewcoach-prod-hybrid}"
NEW_STACK="${COMPUTE_STACK_NAME:-interviewcoach-prod-compute}"
TEMPLATE="${SCRIPT_DIR}/../cloudformation/prod-compute-stack.yaml"
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

write_params_from_prod_env() {
  python3 - "$PARAM_FILE" <<PY
import json, os
params = [
    ("VpcId", os.environ["VPC_ID"]),
    ("PublicSubnetIds", os.environ["PUBLIC_SUBNET_IDS"]),
    ("KeyName", os.environ["KEY_NAME"]),
    ("AmiId", os.environ["AMI_ID"]),
    ("InstanceType", os.environ["INSTANCE_TYPE"]),
    ("InstanceProfileName", os.environ["INSTANCE_PROFILE_NAME"]),
    ("EcrRegistry", os.environ["ECR_REGISTRY"]),
    ("ImageTag", os.environ["IMAGE_TAG"]),
    ("DesiredCapacity", os.environ["ASG_DESIRED_CAPACITY"]),
    ("MinSize", os.environ["ASG_MIN_SIZE"]),
    ("MaxSize", os.environ["ASG_MAX_SIZE"]),
    ("CacheNodeType", os.environ.get("CACHE_NODE_TYPE", "cache.t3.small")),
    ("RdsSecurityGroupId", os.environ["RDS_SECURITY_GROUP_ID"]),
]
open("$PARAM_FILE", "w").write(json.dumps(
    [{"ParameterKey": k, "ParameterValue": v} for k, v in params]
))
PY
}

build_import_from_stack() {
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
    if rtype == "AWS::AutoScaling::AutoScalingGroup":
        return {"AutoScalingGroupName": pid}
    if rtype == "AWS::EC2::LaunchTemplate":
        return {"LaunchTemplateId": pid}
    if rtype == "AWS::ElasticLoadBalancingV2::LoadBalancer":
        return {"LoadBalancerArn": pid}
    if rtype == "AWS::ElasticLoadBalancingV2::TargetGroup":
        return {"TargetGroupArn": pid}
    if rtype == "AWS::ElasticLoadBalancingV2::Listener":
        return {"ListenerArn": pid}
    if rtype == "AWS::EC2::SecurityGroup":
        return {"Id": pid}
    if rtype == "AWS::ElastiCache::SubnetGroup":
        return {"CacheSubnetGroupName": pid}
    if rtype == "AWS::ElastiCache::ReplicationGroup":
        return {"ReplicationGroupId": pid}
    if rtype == "AWS::CloudWatch::Alarm":
        return {"AlarmName": pid}
    if rtype == "AWS::AutoScaling::ScalingPolicy":
        return {"Arn": pid}
    if rtype == "AWS::EC2::SecurityGroupIngress":
        return {"Id": pid}
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
}

import_into_new_stack() {
  python3 "${SCRIPT_DIR}/lib/add-cfn-retain.py" "$TEMPLATE" "$RETAIN_TEMPLATE"
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

  PARAM_OVERRIDES=()
  while IFS= read -r line; do
    PARAM_OVERRIDES+=("$line")
  done < <(python3 "${SCRIPT_DIR}/lib/cfn-format-params.py" deploy "$PARAM_FILE")

  python3 "${SCRIPT_DIR}/lib/cfn-import-params-file.py" "$PARAM_FILE" "$IMPORT_PARAMS_JSON"

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
}

if aws cloudformation describe-stacks --region "$REGION" --stack-name "$OLD_STACK" >/dev/null 2>&1; then
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$OLD_STACK" \
    --query 'Stacks[0].Parameters' --output json > "$PARAM_FILE"

  build_import_from_stack

  python3 "${SCRIPT_DIR}/lib/add-cfn-retain.py" "$TEMPLATE" "$RETAIN_TEMPLATE"

  PARAM_OVERRIDES=()
  while IFS= read -r line; do
    PARAM_OVERRIDES+=("$line")
  done < <(python3 "${SCRIPT_DIR}/lib/cfn-format-params.py" deploy "$PARAM_FILE")

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
  echo "Old stack deleted; resources retained."
else
  echo "Resume: $OLD_STACK already deleted — importing retained resources into $NEW_STACK ..."
  write_params_from_prod_env
  python3 "${SCRIPT_DIR}/lib/build-compute-import-json.py" "$REGION" "$RDS_SECURITY_GROUP_ID" > "$IMPORT_JSON"
  echo "Built $(python3 -c "import json; print(len(json.load(open('$IMPORT_JSON'))))") resources for import."
fi

import_into_new_stack

echo "Renamed $OLD_STACK → $NEW_STACK"
