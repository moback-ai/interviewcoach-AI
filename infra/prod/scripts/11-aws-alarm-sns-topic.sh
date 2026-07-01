#!/usr/bin/env bash
# Create SNS topic for prod CloudWatch alarms and subscribe ALARM_EMAILS.
# Idempotent: re-run safe; updates prod.env ALARM_SNS_TOPIC_ARN when created.
#
# Usage:
#   ALARM_EMAILS=a@x.com,b@y.com bash infra/prod/scripts/11-aws-alarm-sns-topic.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
RAW_EMAILS="${ALARM_EMAILS:-${ALARM_EMAIL:-}}"
TOPIC_NAME="${ALARM_SNS_TOPIC_NAME:-interviewcoach-prod-alarms}"
PROD_ENV="$(dirname "$0")/../prod.env"

if [[ -z "$RAW_EMAILS" ]]; then
  echo "Set ALARM_EMAILS in infra/prod/prod.env (comma-separated) for alarm notifications."
  exit 1
fi

TOPIC_ARN=$(aws sns create-topic --region "$REGION" --name "$TOPIC_NAME" --query TopicArn --output text)
echo "SNS topic: $TOPIC_ARN"

subscribe_email() {
  local email="$1"
  local existing
  existing=$(aws sns list-subscriptions-by-topic --region "$REGION" --topic-arn "$TOPIC_ARN" \
    --query "Subscriptions[?Endpoint=='${email}'].SubscriptionArn | [0]" --output text 2>/dev/null || true)
  if [[ -z "$existing" || "$existing" == "None" ]]; then
    aws sns subscribe --region "$REGION" --topic-arn "$TOPIC_ARN" --protocol email --notification-endpoint "$email" >/dev/null
    echo "Subscribed $email — confirm the AWS SNS confirmation email."
  else
    echo "Subscription exists for $email ($existing)"
  fi
}

IFS=',' read -r -a EMAIL_LIST <<< "${RAW_EMAILS// /}"
for entry in "${EMAIL_LIST[@]}"; do
  email="$(echo "$entry" | tr -d '[:space:]')"
  [[ -n "$email" ]] && subscribe_email "$email"
done

if grep -q '^ALARM_SNS_TOPIC_ARN=' "$PROD_ENV"; then
  if [[ "$(uname)" == "Darwin" ]]; then
    sed -i '' "s|^ALARM_SNS_TOPIC_ARN=.*|ALARM_SNS_TOPIC_ARN=${TOPIC_ARN}|" "$PROD_ENV"
  else
    sed -i "s|^ALARM_SNS_TOPIC_ARN=.*|ALARM_SNS_TOPIC_ARN=${TOPIC_ARN}|" "$PROD_ENV"
  fi
else
  printf '\nALARM_SNS_TOPIC_ARN=%s\n' "$TOPIC_ARN" >> "$PROD_ENV"
fi

export ALARM_SNS_TOPIC_ARN="$TOPIC_ARN"
bash "$(dirname "$0")/12-aws-cloudwatch-alarms.sh"

echo "Alarm SNS setup complete."
