#!/usr/bin/env bash
# Roll out a pre-built ECR image to the PROD ASG (launch template + instance refresh).
# Image must already exist in ECR (built by GitHub Actions).
#
# Usage: IMAGE_TAG=prod-20260630 bash infra/prod/scripts/06-code-deploy-api-asg.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
COMPUTE_TEMPLATE="$(dirname "$0")/../cloudformation/prod-compute-stack.yaml"

resolve_stack_name() {
  local preferred="$1"
  shift
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
ASG="${ASG_NAME:-interviewcoach-prod-api-asg}"
ECR_REGISTRY="${ECR_REGISTRY:?Set ECR_REGISTRY}"
IMAGE_TAG="${IMAGE_TAG:?Set IMAGE_TAG}"
VPC_ID="${VPC_ID:?Set VPC_ID}"
PUBLIC_SUBNETS="${PUBLIC_SUBNET_IDS:?Set PUBLIC_SUBNET_IDS}"

resume_asg_scheduled_actions() {
  aws autoscaling resume-processes \
    --region "$REGION" \
    --auto-scaling-group-name "$ASG" \
    --scaling-processes ScheduledActions >/dev/null 2>&1 || true
}

echo "Suspending ASG scheduled scaling for deploy ..."
aws autoscaling suspend-processes \
  --region "$REGION" \
  --auto-scaling-group-name "$ASG" \
  --scaling-processes ScheduledActions
trap resume_asg_scheduled_actions EXIT

echo "Updating compute stack $COMPUTE_STACK with IMAGE_TAG=$IMAGE_TAG ..."
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$COMPUTE_STACK" \
  --template-file "$COMPUTE_TEMPLATE" \
  --parameter-overrides \
    VpcId="$VPC_ID" \
    PublicSubnetIds="$PUBLIC_SUBNETS" \
    KeyName="${KEY_NAME:-interviewcoach-key-v2}" \
    AmiId="${AMI_ID:-ami-0a1b0c508e1fa9fce}" \
    InstanceType="${INSTANCE_TYPE:-c6i.xlarge}" \
    InstanceProfileName="${INSTANCE_PROFILE_NAME:-InterviewCoachBackendSecretsProfile}" \
    EcrRegistry="$ECR_REGISTRY" \
    ImageTag="$IMAGE_TAG" \
    DesiredCapacity="${ASG_DESIRED_CAPACITY:-2}" \
    MinSize="${ASG_MIN_SIZE:-2}" \
    MaxSize="${ASG_MAX_SIZE:-4}" \
    RdsSecurityGroupId="${RDS_SECURITY_GROUP_ID:?Set RDS_SECURITY_GROUP_ID}" \
  --no-fail-on-empty-changeset

REFRESH_ID=$(aws autoscaling start-instance-refresh \
  --region "$REGION" \
  --auto-scaling-group-name "$ASG" \
  --preferences "MinHealthyPercentage=50,InstanceWarmup=300" \
  --query InstanceRefreshId --output text)
echo "Instance refresh started: $REFRESH_ID"

for i in $(seq 1 40); do
  STATUS=$(aws autoscaling describe-instance-refreshes \
    --region "$REGION" \
    --auto-scaling-group-name "$ASG" \
    --instance-refresh-ids "$REFRESH_ID" \
    --query 'InstanceRefreshes[0].Status' --output text 2>/dev/null || echo "Pending")
  echo "Refresh status: $STATUS"
  [[ "$STATUS" == "Successful" ]] && break
  [[ "$STATUS" == "Failed" || "$STATUS" == "Cancelled" ]] && exit 1
  sleep 30
done

trap - EXIT
resume_asg_scheduled_actions

ALB_DNS="${ALB_DNS_NAME:-}"
if [[ -n "$ALB_DNS" ]]; then
  curl -fsS "http://${ALB_DNS}/api/health" | head -c 400 || true
fi
echo "ASG deploy complete. Image: ${ECR_REGISTRY}/interviewcoach-api:${IMAGE_TAG}"
