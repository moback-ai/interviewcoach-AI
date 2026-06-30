#!/usr/bin/env bash
# CloudWatch Logs for prod API + read-only IAM for InterviewCoach-Developers.
#
# 1. Creates log group /interviewcoach/prod/api
# 2. Updates API instance IAM policy (scoped log write)
# 3. Attaches developer read-only logs policy (via devsecops apply-iam-policies.sh)
# 4. Updates compute stack launch template (awslogs in docker compose) + instance refresh
#
# Usage: CONFIRM=YES bash infra/prod/scripts/17-aws-cloudwatch-api-logs.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REGION="${AWS_REGION:-ap-south-1}"
LOG_GROUP="${API_LOG_GROUP:-/interviewcoach/prod/api}"
RETENTION="${API_LOG_RETENTION_DAYS:-30}"
COMPUTE_STACK="${COMPUTE_STACK_NAME:-interviewcoach-prod-compute}"
COMPUTE_TEMPLATE="${SCRIPT_DIR}/../cloudformation/prod-compute-stack.yaml"
ASG="${ASG_NAME:-interviewcoach-prod-api-asg}"
DEVSECOPS_ROOT="${DEVSECOPS_PLATFORM_ROOT:-$(cd "${SCRIPT_DIR}/../../../../devsecops-platform" 2>/dev/null && pwd || true)}"

if [[ "${CONFIRM:-}" != "YES" ]]; then
  echo "Sets up CloudWatch Logs at ${LOG_GROUP} and read-only dev IAM."
  echo "Re-run: CONFIRM=YES bash $0"
  exit 1
fi

echo "=== 1/4 Log group ${LOG_GROUP} ==="
if aws logs describe-log-groups --region "$REGION" --log-group-name-prefix "$LOG_GROUP" \
  --query "logGroups[?logGroupName=='${LOG_GROUP}'].logGroupName" --output text | grep -q .; then
  echo "Log group exists."
else
  aws logs create-log-group --region "$REGION" --log-group-name "$LOG_GROUP"
  echo "Created log group."
fi
aws logs put-retention-policy --region "$REGION" --log-group-name "$LOG_GROUP" \
  --retention-in-days "$RETENTION"

echo "=== 2/4 API instance IAM (log write to /interviewcoach/prod/*) ==="
bash "${SCRIPT_DIR}/04-aws-iam-attach.sh"

echo "=== 3/4 Developer read-only logs policy ==="
if [[ -f "${DEVSECOPS_ROOT}/scripts/apply-iam-policies.sh" ]]; then
  cp "${SCRIPT_DIR}/../iam/developer-logs-readonly.json" \
    "${DEVSECOPS_ROOT}/iam/policies/developer-logs-readonly.json"
  bash "${DEVSECOPS_ROOT}/scripts/apply-iam-policies.sh" --apply
else
  echo "WARN: devsecops-platform not found — attach developer-logs-readonly.json manually."
fi

echo "=== 4/4 Compute stack launch template (awslogs) + instance refresh ==="
resume_asg_scheduled_actions() {
  aws autoscaling resume-processes --region "$REGION" \
    --auto-scaling-group-name "$ASG" --scaling-processes ScheduledActions >/dev/null 2>&1 || true
}
aws autoscaling suspend-processes --region "$REGION" \
  --auto-scaling-group-name "$ASG" --scaling-processes ScheduledActions
trap resume_asg_scheduled_actions EXIT

aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$COMPUTE_STACK" \
  --template-file "$COMPUTE_TEMPLATE" \
  --parameter-overrides \
    VpcId="${VPC_ID:?Set VPC_ID}" \
    PublicSubnetIds="${PUBLIC_SUBNET_IDS:?Set PUBLIC_SUBNET_IDS}" \
    KeyName="${KEY_NAME:-interviewcoach-key-v2}" \
    AmiId="${AMI_ID:-ami-0a1b0c508e1fa9fce}" \
    InstanceType="${INSTANCE_TYPE:-c6i.xlarge}" \
    InstanceProfileName="${INSTANCE_PROFILE_NAME:-InterviewCoachBackendSecretsProfile}" \
    EcrRegistry="${ECR_REGISTRY:?Set ECR_REGISTRY}" \
    ImageTag="${IMAGE_TAG:?Set IMAGE_TAG}" \
    ApiLogGroup="$LOG_GROUP" \
    DesiredCapacity="${ASG_DESIRED_CAPACITY:-1}" \
    MinSize="${ASG_MIN_SIZE:-1}" \
    MaxSize="${ASG_MAX_SIZE:-4}" \
    RdsSecurityGroupId="${RDS_SECURITY_GROUP_ID:?Set RDS_SECURITY_GROUP_ID}" \
  --no-fail-on-empty-changeset

REFRESH_ID=$(aws autoscaling start-instance-refresh \
  --region "$REGION" \
  --auto-scaling-group-name "$ASG" \
  --preferences "MinHealthyPercentage=0,InstanceWarmup=300" \
  --query InstanceRefreshId --output text)
echo "Instance refresh: $REFRESH_ID (new nodes will ship logs to CloudWatch)"

trap - EXIT
resume_asg_scheduled_actions

echo ""
echo "Done. Developers: AWS Console → CloudWatch → Log groups → ${LOG_GROUP}"
echo "Or Logs Insights → filter @message like /ERROR/"
