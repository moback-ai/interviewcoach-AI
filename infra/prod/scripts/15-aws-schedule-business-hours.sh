#!/usr/bin/env bash
# ASG business hours: 10:00–19:00 IST (API nodes only). RDS/ElastiCache stay 24/7.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
source "$(dirname "$0")/load-prod-env.sh"
REGION="${AWS_REGION:-ap-south-1}"
ASG="${ASG_NAME:-interviewcoach-prod-api-asg}"
UP_CRON="${ASG_SCHEDULE_UP_CRON:-30 4 * * *}"
DOWN_CRON="${ASG_SCHEDULE_DOWN_CRON:-30 13 * * *}"

aws autoscaling put-scheduled-update-group-action --region "$REGION" \
  --auto-scaling-group-name "$ASG" --scheduled-action-name interviewcoach-prod-scale-up \
  --recurrence "$UP_CRON" --desired-capacity "${ASG_DESIRED_CAPACITY:-1}" \
  --min-size "${ASG_MIN_SIZE:-1}" --max-size "${ASG_MAX_SIZE:-4}"

aws autoscaling put-scheduled-update-group-action --region "$REGION" \
  --auto-scaling-group-name "$ASG" --scheduled-action-name interviewcoach-prod-scale-down \
  --recurrence "$DOWN_CRON" --desired-capacity 0 --min-size 0 --max-size 0

echo "Scheduled $ASG: up 10:00 IST, down 19:00 IST (7pm)."
