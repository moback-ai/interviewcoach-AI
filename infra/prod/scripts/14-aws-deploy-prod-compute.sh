#!/usr/bin/env bash
# Deploy PROD compute (ALB + ASG + ElastiCache + RDS Proxy) and cut over CloudFront.
#
# Usage: CONFIRM=YES bash infra/prod/scripts/14-aws-deploy-prod-compute.sh
set -euo pipefail

SCRIPT_DIR="$(dirname "$0")"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
COMPUTE_TEMPLATE="$SCRIPT_DIR/../cloudformation/prod-compute-stack.yaml"
PROXY_TEMPLATE="$SCRIPT_DIR/../cloudformation/prod-rds-proxy.yaml"
VPC_ID="${VPC_ID:?Set VPC_ID}"
PUBLIC_SUBNETS="${PUBLIC_SUBNET_IDS:-subnet-00662d4d6964a6ee4,subnet-090e9d10afc24205f,subnet-0f1a1e9146d12a37b}"
RDS_SG="${RDS_SECURITY_GROUP_ID:-sg-0309dacce73c934dd}"
RDS_ID="${RDS_INSTANCE_ID:-interviewcoach-db}"
SECRET_ID="${SECRET_ID:-interviewcoach/prod/app}"
PROXY_SECRET_ID="${RDS_PROXY_SECRET_ID:-interviewcoach/prod/rds-proxy}"
ECR_REGISTRY="${ECR_REGISTRY:?}"
IMAGE_TAG="${IMAGE_TAG:-prod-20260630}"
INSTANCE_TYPE="${INSTANCE_TYPE:-c6i.xlarge}"
CF_DIST_ID="${CF_DIST_ID:?}"
PROD_ENV="$SCRIPT_DIR/../prod.env"

resolve_stack_name() {
  local preferred="$1"
  shift
  local legacy
  if aws cloudformation describe-stacks --region "$REGION" --stack-name "$preferred" >/dev/null 2>&1; then
    echo "$preferred"
    return
  fi
  for legacy in "$@"; do
    if aws cloudformation describe-stacks --region "$REGION" --stack-name "$legacy" >/dev/null 2>&1; then
      echo "$legacy"
      return
    fi
  done
  echo "$preferred"
}

COMPUTE_STACK=$(resolve_stack_name \
  "${COMPUTE_STACK_NAME:-interviewcoach-prod-compute}" \
  "interviewcoach-prod-hybrid")
PROXY_STACK=$(resolve_stack_name \
  "${PROXY_STACK_NAME:-interviewcoach-prod-proxy}" \
  "interviewcoach-prod-rds-proxy")

if [[ "${CONFIRM:-}" != "YES" ]]; then
  echo "Deploys PROD compute: ALB + ASG (${INSTANCE_TYPE}) + ElastiCache + RDS Multi-AZ + RDS Proxy."
  echo "CloudFront API origin switches to ALB."
  echo "Re-run: CONFIRM=YES bash $0"
  exit 1
fi

echo "=== Step 1: PROD compute stack (ALB + ASG + ElastiCache) ==="
echo "Stack: $COMPUTE_STACK"
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$COMPUTE_STACK" \
  --template-file "$COMPUTE_TEMPLATE" \
  --parameter-overrides \
    VpcId="$VPC_ID" \
    PublicSubnetIds="$PUBLIC_SUBNETS" \
    KeyName="${KEY_NAME:-interviewcoach-key-v2}" \
    AmiId="${AMI_ID:-ami-0a1b0c508e1fa9fce}" \
    InstanceType="$INSTANCE_TYPE" \
    InstanceProfileName="${INSTANCE_PROFILE_NAME:-InterviewCoachBackendSecretsProfile}" \
    EcrRegistry="$ECR_REGISTRY" \
    ImageTag="$IMAGE_TAG" \
    DesiredCapacity="${ASG_DESIRED_CAPACITY:-2}" \
    MinSize="${ASG_MIN_SIZE:-2}" \
    MaxSize="${ASG_MAX_SIZE:-4}" \
    RdsSecurityGroupId="$RDS_SG" \
  --no-fail-on-empty-changeset

stack_output() {
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$COMPUTE_STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

ALB_DNS=$(stack_output AlbDnsName)
REDIS_URL=$(stack_output RedisUrl)
API_SG=$(stack_output ApiSecurityGroupId)
ASG_NAME=$(stack_output AutoScalingGroupName)

echo "ALB:    $ALB_DNS"
echo "Redis:  $REDIS_URL"
echo "ASG:    $ASG_NAME"

echo ""
echo "=== Step 2: RDS Multi-AZ ==="
MULTI=$(aws rds describe-db-instances --region "$REGION" --db-instance-identifier "$RDS_ID" \
  --query 'DBInstances[0].MultiAZ' --output text)
if [[ "$MULTI" != "True" ]]; then
  echo "Enabling Multi-AZ on $RDS_ID (brief failover possible) ..."
  aws rds modify-db-instance \
    --region "$REGION" \
    --db-instance-identifier "$RDS_ID" \
    --multi-az \
    --apply-immediately
  aws rds wait db-instance-available --region "$REGION" --db-instance-identifier "$RDS_ID"
else
  echo "RDS already Multi-AZ."
fi

echo ""
echo "=== Step 3: RDS Proxy secret + stack ==="
SECRET_TMP=$(mktemp)
trap 'rm -f "$SECRET_TMP"' EXIT
aws secretsmanager get-secret-value --region "$REGION" --secret-id "$SECRET_ID" \
  --query SecretString --output text > "$SECRET_TMP"
python3 - "$SECRET_TMP" "$PROXY_SECRET_ID" <<'PY'
import json, sys, subprocess, os

src_path = sys.argv[1]
proxy_id = sys.argv[2]
src = json.load(open(src_path))
user = src.get("DB_USER") or src.get("username")
password = src.get("DB_PASSWORD") or src.get("password")
if not user or not password:
    raise SystemExit("DB_USER/DB_PASSWORD missing in app secret")
payload = json.dumps({"username": user, "password": password})
region = os.environ.get("AWS_REGION", "ap-south-1")
try:
    subprocess.run(
        ["aws", "secretsmanager", "describe-secret", "--region", region, "--secret-id", proxy_id],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["aws", "secretsmanager", "put-secret-value", "--region", region,
         "--secret-id", proxy_id, "--secret-string", payload],
        check=True,
    )
    print(f"Updated proxy secret: {proxy_id}")
except subprocess.CalledProcessError:
    subprocess.run(
        ["aws", "secretsmanager", "create-secret", "--region", region,
         "--name", proxy_id, "--description", "RDS Proxy credentials",
         "--secret-string", payload],
        check=True,
    )
    print(f"Created proxy secret: {proxy_id}")
PY
PROXY_SECRET_ARN=$(aws secretsmanager describe-secret --region "$REGION" --secret-id "$PROXY_SECRET_ID" \
  --query ARN --output text)

echo "Proxy stack: $PROXY_STACK"
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$PROXY_STACK" \
  --template-file "$PROXY_TEMPLATE" \
  --parameter-overrides \
    VpcId="$VPC_ID" \
    SubnetIds="$PUBLIC_SUBNETS" \
    DbInstanceIdentifier="$RDS_ID" \
    DbSecretArn="$PROXY_SECRET_ARN" \
    ApiSecurityGroupId="$API_SG" \
    RdsSecurityGroupId="$RDS_SG" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset

PROXY_HOST=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$PROXY_STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='RdsProxyEndpoint'].OutputValue" --output text)
echo "RDS Proxy: $PROXY_HOST"

echo ""
echo "=== Step 4: Patch Secrets Manager (Redis + RDS Proxy) ==="
export REDIS_URL="$REDIS_URL"
export DB_HOST="$PROXY_HOST"
export INFRA_LAYOUT="prod"
bash "$SCRIPT_DIR/03c-patch-prod-secret.sh"

echo ""
echo "=== Step 5: Wait for ASG healthy targets ==="
TG_ARN=$(stack_output TargetGroupArn)
for i in $(seq 1 40); do
  HEALTHY=$(aws elbv2 describe-target-health --region "$REGION" \
    --target-group-arn "$TG_ARN" \
    --query 'length(TargetHealthDescriptions[?TargetHealth.State==`healthy`])' --output text 2>/dev/null || echo 0)
  echo "Healthy targets: $HEALTHY"
  [[ "${HEALTHY:-0}" -ge 1 ]] && break
  sleep 15
done

curl -fsS "http://${ALB_DNS}/api/health" | head -c 400 || echo "ALB health pending (instances still booting)"

echo ""
echo "=== Step 6: CloudFront API origin -> ALB ==="
ETAG=$(aws cloudfront get-distribution-config --id "$CF_DIST_ID" --query ETag --output text)
DIST_TMP=$(mktemp)
aws cloudfront get-distribution-config --id "$CF_DIST_ID" --query DistributionConfig --output json > "$DIST_TMP"
python3 - "$DIST_TMP" "$ALB_DNS" <<'PY'
import json, sys
path, alb = sys.argv[1:3]
cfg = json.load(open(path))
for origin in cfg.get("Origins", {}).get("Items", []):
    if origin.get("Id") == "ApiOrigin":
        origin["DomainName"] = alb
        break
else:
    raise SystemExit("ApiOrigin not found in CloudFront config")
json.dump(cfg, open(path, "w"))
PY
aws cloudfront update-distribution --id "$CF_DIST_ID" --if-match "$ETAG" \
  --distribution-config "file://${DIST_TMP}"
rm -f "$DIST_TMP"
echo "CloudFront origin updated to $ALB_DNS (propagation ~2-5 min)"

echo ""
echo "=== Step 7: Update prod.env ==="
python3 - "$PROD_ENV" "$ALB_DNS" "$REDIS_URL" "$PROXY_HOST" "$ASG_NAME" "$API_SG" "$COMPUTE_STACK" "$PROXY_STACK" <<'PY'
import sys
path, alb, redis_url, proxy, asg, api_sg, compute_stack, proxy_stack = sys.argv[1:9]
updates = {
    "INFRA_LAYOUT": "prod",
    "COMPUTE_STACK_NAME": compute_stack,
    "PROXY_STACK_NAME": proxy_stack,
    "ALB_DNS_NAME": alb,
    "API_ORIGIN_DOMAIN": alb,
    "REDIS_URL": redis_url,
    "DB_HOST": proxy,
    "ASG_NAME": asg,
    "API_ASG_SG_ID": api_sg,
    "INSTANCE_TYPE": "c6i.xlarge",
}
drop_prefixes = ("HYBRID_",)
lines = open(path).read().splitlines()
out, seen = [], set()
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line and not line.strip().startswith("#") else ""
    if key.startswith(drop_prefixes):
        continue
    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)
for k, v in updates.items():
    if k not in seen:
        out.append(f"{k}={v}")
open(path, "w").write("\n".join(out) + "\n")
PY

echo ""
echo "=== PROD compute deploy complete ==="
echo "  ALB:         http://${ALB_DNS}/api/health"
echo "  Site:        https://www.ugaanlabs.ai/api/health"
echo "  Redis:       $REDIS_URL"
echo "  DB (proxy):  $PROXY_HOST"
