#!/usr/bin/env bash
# Deploy API image to prod ASG: bump launch template + rolling instance refresh.
# Usage: IMAGE_TAG=prod-20260701-abc1234 bash infra/prod/scripts/06-code-deploy-api-asg.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REGION="${AWS_REGION:-ap-south-1}"
ASG="${ASG_NAME:-interviewcoach-prod-api-asg}"
ECR_REGISTRY="${ECR_REGISTRY:?Set ECR_REGISTRY}"
IMAGE_TAG="${IMAGE_TAG:?Set IMAGE_TAG}"

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

LT_ID=$(aws autoscaling describe-auto-scaling-groups \
  --region "$REGION" \
  --auto-scaling-group-names "$ASG" \
  --query 'AutoScalingGroups[0].LaunchTemplate.LaunchTemplateId' \
  --output text)
[[ -n "$LT_ID" && "$LT_ID" != "None" ]] || { echo "No launch template for ASG $ASG"; exit 1; }

echo "Launch template $LT_ID -> ${ECR_REGISTRY}/interviewcoach-api:${IMAGE_TAG}"
python3 "${SCRIPT_DIR}/lib/bump-launch-template-image.py" "$REGION" "$LT_ID" "$ECR_REGISTRY" "$IMAGE_TAG" >/dev/null

aws autoscaling update-auto-scaling-group \
  --region "$REGION" \
  --auto-scaling-group-name "$ASG" \
  --launch-template "LaunchTemplateId=${LT_ID},Version=\$Latest"

ACTIVE_REFRESH=$(aws autoscaling describe-instance-refreshes \
  --region "$REGION" \
  --auto-scaling-group-name "$ASG" \
  --query 'InstanceRefreshes[?Status==`InProgress` || Status==`Cancelling` || Status==`Pending`].InstanceRefreshId | [0]' \
  --output text 2>/dev/null || echo "None")
if [[ -n "$ACTIVE_REFRESH" && "$ACTIVE_REFRESH" != "None" ]]; then
  echo "Cancelling in-progress refresh $ACTIVE_REFRESH ..."
  aws autoscaling cancel-instance-refresh --region "$REGION" --auto-scaling-group-name "$ASG"
  for _ in $(seq 1 24); do
    BLOCKING=$(aws autoscaling describe-instance-refreshes \
      --region "$REGION" \
      --auto-scaling-group-name "$ASG" \
      --query 'InstanceRefreshes[?Status==`InProgress` || Status==`Cancelling` || Status==`Pending`].InstanceRefreshId | [0]' \
      --output text 2>/dev/null || echo "None")
    [[ -z "$BLOCKING" || "$BLOCKING" == "None" ]] && break
    sleep 10
  done
fi

REFRESH_ID=$(aws autoscaling start-instance-refresh \
  --region "$REGION" \
  --auto-scaling-group-name "$ASG" \
  --preferences "MinHealthyPercentage=50,InstanceWarmup=90" \
  --query InstanceRefreshId --output text)
echo "Instance refresh: $REFRESH_ID"

STATUS="Pending"
for _ in $(seq 1 40); do
  STATUS=$(aws autoscaling describe-instance-refreshes \
    --region "$REGION" \
    --auto-scaling-group-name "$ASG" \
    --instance-refresh-ids "$REFRESH_ID" \
    --query 'InstanceRefreshes[0].Status' --output text 2>/dev/null || echo "Pending")
  echo "  status: $STATUS"
  [[ "$STATUS" == "Successful" ]] && break
  [[ "$STATUS" == "Failed" || "$STATUS" == "Cancelled" ]] && exit 1
  sleep 20
done
[[ "$STATUS" == "Successful" ]] || { echo "Refresh did not finish: $STATUS"; exit 1; }

trap - EXIT
resume_asg_scheduled_actions

if [[ -n "${ALB_DNS_NAME:-}" ]]; then
  curl -fsS --max-time 10 "http://${ALB_DNS_NAME}/api/health/ready" | head -c 200 || true
  echo
fi
echo "API deploy done: ${IMAGE_TAG}"
