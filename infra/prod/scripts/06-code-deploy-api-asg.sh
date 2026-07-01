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
if [[ -z "$LT_ID" || "$LT_ID" == "None" ]]; then
  echo "Could not resolve launch template for ASG $ASG"
  exit 1
fi

echo "Bumping launch template $LT_ID to image ${ECR_REGISTRY}/interviewcoach-api:${IMAGE_TAG} ..."
NEW_LT_VERSION=$(python3 "${SCRIPT_DIR}/lib/bump-launch-template-image.py" \
  "$REGION" "$LT_ID" "$ECR_REGISTRY" "$IMAGE_TAG")
echo "Created launch template version $NEW_LT_VERSION"

aws autoscaling update-auto-scaling-group \
  --region "$REGION" \
  --auto-scaling-group-name "$ASG" \
  --launch-template "LaunchTemplateId=${LT_ID},Version=\$Latest"

ACTIVE_REFRESH=$(aws autoscaling describe-instance-refreshes \
  --region "$REGION" \
  --auto-scaling-group-name "$ASG" \
  --query 'InstanceRefreshes[?Status==`InProgress`].InstanceRefreshId | [0]' \
  --output text 2>/dev/null || echo "None")
if [[ -n "$ACTIVE_REFRESH" && "$ACTIVE_REFRESH" != "None" ]]; then
  echo "Cancelling stuck instance refresh $ACTIVE_REFRESH (required before new rollout) ..."
  aws autoscaling cancel-instance-refresh \
    --region "$REGION" \
    --auto-scaling-group-name "$ASG"
  for _ in $(seq 1 20); do
    ST=$(aws autoscaling describe-instance-refreshes \
      --region "$REGION" \
      --auto-scaling-group-name "$ASG" \
      --instance-refresh-ids "$ACTIVE_REFRESH" \
      --query 'InstanceRefreshes[0].Status' --output text 2>/dev/null || echo "Cancelled")
    echo "Prior refresh status: $ST"
    [[ "$ST" != "InProgress" ]] && break
    sleep 15
  done
fi

REFRESH_ID=$(aws autoscaling start-instance-refresh \
  --region "$REGION" \
  --auto-scaling-group-name "$ASG" \
  --preferences "MinHealthyPercentage=50,InstanceWarmup=120" \
  --query InstanceRefreshId --output text)
echo "Instance refresh started: $REFRESH_ID"

for i in $(seq 1 60); do
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
[[ "$STATUS" == "Successful" ]] || { echo "Instance refresh did not complete: $STATUS"; exit 1; }

trap - EXIT
resume_asg_scheduled_actions

ALB_DNS="${ALB_DNS_NAME:-}"
if [[ -n "$ALB_DNS" ]]; then
  curl -fsS --max-time 15 "http://${ALB_DNS}/api/health" | head -c 400 || true
fi
echo "ASG deploy complete. Image: ${ECR_REGISTRY}/interviewcoach-api:${IMAGE_TAG}"
