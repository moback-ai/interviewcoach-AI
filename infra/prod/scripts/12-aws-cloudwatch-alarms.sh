#!/usr/bin/env bash
# Create basic CloudWatch alarms for prod API EC2 + RDS. Idempotent-ish (skips if exists).
#
# Usage: bash infra/prod/scripts/12-aws-cloudwatch-alarms.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
INSTANCE_ID="${API_INSTANCE_ID:?Set API_INSTANCE_ID}"
RDS_ID="${RDS_INSTANCE_ID:-interviewcoach-db}"
SNS_TOPIC_ARN="${ALARM_SNS_TOPIC_ARN:-}"

put_alarm() {
  local name="$1"
  shift
  if aws cloudwatch describe-alarms --region "$REGION" --alarm-names "$name" \
    --query 'length(MetricAlarms)' --output text 2>/dev/null | grep -q '^1$'; then
    echo "Alarm exists: $name (skip)"
    return 0
  fi
  if [[ -n "$SNS_TOPIC_ARN" ]]; then
    aws cloudwatch put-metric-alarm --region "$REGION" --alarm-name "$name" "$@" \
      --alarm-actions "$SNS_TOPIC_ARN" --ok-actions "$SNS_TOPIC_ARN"
  else
    aws cloudwatch put-metric-alarm --region "$REGION" --alarm-name "$name" "$@"
  fi
  echo "Created alarm: $name"
}

put_alarm "interviewcoach-prod-ec2-cpu-high" \
  --alarm-description "Prod API EC2 CPU > 80% for 10 min" \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions "Name=InstanceId,Value=$INSTANCE_ID" \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --treat-missing-data notBreaching

put_alarm "interviewcoach-prod-ec2-status-check" \
  --alarm-description "Prod API EC2 status check failed" \
  --namespace AWS/EC2 \
  --metric-name StatusCheckFailed \
  --dimensions "Name=InstanceId,Value=$INSTANCE_ID" \
  --statistic Maximum \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 0 \
  --comparison-operator GreaterThanThreshold \
  --treat-missing-data breaching

put_alarm "interviewcoach-prod-rds-cpu-high" \
  --alarm-description "Prod RDS CPU > 80% for 15 min" \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions "Name=DBInstanceIdentifier,Value=$RDS_ID" \
  --statistic Average \
  --period 300 \
  --evaluation-periods 3 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --treat-missing-data notBreaching

put_alarm "interviewcoach-prod-rds-storage-low" \
  --alarm-description "Prod RDS free storage < 5 GB" \
  --namespace AWS/RDS \
  --metric-name FreeStorageSpace \
  --dimensions "Name=DBInstanceIdentifier,Value=$RDS_ID" \
  --statistic Average \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5368709120 \
  --comparison-operator LessThanThreshold \
  --treat-missing-data notBreaching

echo ""
echo "CloudWatch alarms configured."
echo "Optional: set ALARM_SNS_TOPIC_ARN in prod.env for email/SMS notifications."
echo "External uptime: monitor https://www.ugaanlabs.ai/api/health"
