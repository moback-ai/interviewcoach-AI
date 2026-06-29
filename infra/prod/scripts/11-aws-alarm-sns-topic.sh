#!/usr/bin/env bash
# Create SNS topic for prod CloudWatch alarms and subscribe ALARM_EMAIL.
# Idempotent: re-run safe; updates prod.env ALARM_SNS_TOPIC_ARN when created.
#
# Usage:
#   ALARM_EMAIL=you@example.com bash infra/prod/scripts/11-aws-alarm-sns-topic.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
EMAIL="${ALARM_EMAIL:-}"
TOPIC_NAME="${ALARM_SNS_TOPIC_NAME:-interviewcoach-prod-alarms}"
PROD_ENV="$(dirname "$0")/../prod.env"

if [[ -z "$EMAIL" ]]; then
  echo "Set ALARM_EMAIL in infra/prod/prod.env (or env) for alarm notifications."
  exit 1
fi

TOPIC_ARN=$(aws sns create-topic --region "$REGION" --name "$TOPIC_NAME" --query TopicArn --output text)
echo "SNS topic: $TOPIC_ARN"

EXISTING=$(aws sns list-subscriptions-by-topic --region "$REGION" --topic-arn "$TOPIC_ARN" \
  --query "Subscriptions[?Endpoint=='${EMAIL}'].SubscriptionArn | [0]" --output text 2>/dev/null || true)
if [[ -z "$EXISTING" || "$EXISTING" == "None" ]]; then
  aws sns subscribe --region "$REGION" --topic-arn "$TOPIC_ARN" --protocol email --notification-endpoint "$EMAIL" >/dev/null
  echo "Subscribed $EMAIL — confirm the AWS SNS confirmation email."
else
  echo "Subscription exists for $EMAIL ($EXISTING)"
fi

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
