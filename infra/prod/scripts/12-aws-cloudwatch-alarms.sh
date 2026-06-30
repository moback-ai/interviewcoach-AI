#!/usr/bin/env bash
# CloudWatch alarms for prod ASG + RDS. Removes legacy single-EC2 alarms if present.
#
# Usage: bash infra/prod/scripts/12-aws-cloudwatch-alarms.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
ASG="${ASG_NAME:-interviewcoach-prod-api-asg}"
RDS_ID="${RDS_INSTANCE_ID:-interviewcoach-db}"
SNS_TOPIC_ARN="${ALARM_SNS_TOPIC_ARN:-}"

delete_alarm_if_exists() {
  local name="$1"
  if aws cloudwatch describe-alarms --region "$REGION" --alarm-names "$name" \
    --query 'length(MetricAlarms)' --output text 2>/dev/null | grep -q '^1$'; then
    aws cloudwatch delete-alarms --region "$REGION" --alarm-names "$name"
    echo "Deleted legacy alarm: $name"
  fi
}

put_alarm() {
  local name="$1"
  shift
  local action="Created"
  if aws cloudwatch describe-alarms --region "$REGION" --alarm-names "$name" \
    --query 'length(MetricAlarms)' --output text 2>/dev/null | grep -q '^1$'; then
    action="Updated"
  fi
  if [[ -n "$SNS_TOPIC_ARN" ]]; then
    aws cloudwatch put-metric-alarm --region "$REGION" --alarm-name "$name" "$@" \
      --alarm-actions "$SNS_TOPIC_ARN" --ok-actions "$SNS_TOPIC_ARN"
  else
    aws cloudwatch put-metric-alarm --region "$REGION" --alarm-name "$name" "$@"
  fi
  echo "${action} alarm: $name"
}

# Retired with legacy single-EC2 stack
delete_alarm_if_exists "interviewcoach-prod-ec2-cpu-high"
delete_alarm_if_exists "interviewcoach-prod-ec2-status-check"

put_alarm "interviewcoach-prod-asg-cpu-high" \
  --alarm-description "Prod API ASG average CPU > 80% for 10 min" \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions "Name=AutoScalingGroupName,Value=$ASG" \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --treat-missing-data notBreaching

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
echo "CloudWatch alarms configured (ASG + RDS)."
echo "ASG scale alarms remain in the compute CloudFormation stack."
echo "External uptime: monitor https://www.ugaanlabs.ai/api/health (10:00–19:00 IST)"
