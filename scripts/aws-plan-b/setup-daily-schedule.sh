#!/usr/bin/env bash
# Daily schedule: START 8:00 AM IST (02:30 UTC), STOP 8:00 PM IST (14:30 UTC)
#
# Usage:
#   ./setup-daily-schedule.sh           # dry-run
#   ./setup-daily-schedule.sh --apply
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.env"
[[ -f "${SCRIPT_DIR}/outputs.env" ]] && source "${SCRIPT_DIR}/outputs.env"

APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

FUNCTION_NAME="${SCHEDULE_LAMBDA_NAME:-interviewcoach-daily-schedule}"
ROLE_NAME="${SCHEDULE_ROLE_NAME:-interviewcoach-schedule-lambda-role}"
SCHEDULER_ROLE_NAME="${ROLE_NAME}-invoke"
START_SCHEDULE="${SCHEDULE_START_NAME:-interviewcoach-start-8am-ist}"
STOP_SCHEDULE="${SCHEDULE_STOP_NAME:-interviewcoach-stop-8pm-ist}"
CRON_START="cron(30 2 * * ? *)"
CRON_STOP="cron(30 14 * * ? *)"

API_ID="${API_INSTANCE_ID:-}"
if [[ -n "$API_ID" ]]; then
  EC2_LIST="${FRONTEND_INSTANCE_ID},${API_ID},${AI_INSTANCE_ID}"
else
  EC2_LIST="${FRONTEND_INSTANCE_ID},${AI_INSTANCE_ID}"
fi

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
run() { if [[ "$APPLY" -eq 1 ]]; then log "RUN: $*"; eval "$@"; else log "DRY-RUN: $*"; fi; }

log "EC2: $EC2_LIST | RDS: $RDS_INSTANCE_ID"
log "Start 8:00 AM IST = $CRON_START UTC"
log "Stop  8:00 PM IST = $CRON_STOP UTC"

ZIP="${SCRIPT_DIR}/lambda/schedule_handler.zip"
rm -f "$ZIP"
(cd "${SCRIPT_DIR}/lambda" && zip -q schedule_handler.zip schedule_handler.py)

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
LAMBDA_ARN="arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"
SCHED_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${SCHEDULER_ROLE_NAME}"

if [[ "$APPLY" -eq 1 ]]; then
  if ! aws iam get-role --role-name "$ROLE_NAME" &>/dev/null; then
    aws iam create-role --role-name "$ROLE_NAME" \
      --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
    aws iam attach-role-policy --role-name "$ROLE_NAME" \
      --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name ec2-rds \
      --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["ec2:StartInstances","ec2:StopInstances","ec2:DescribeInstances","rds:StartDBInstance","rds:StopDBInstance","rds:DescribeDBInstances"],"Resource":"*"}]}'
    sleep 10
  fi

  if ! aws iam get-role --role-name "$SCHEDULER_ROLE_NAME" &>/dev/null; then
    aws iam create-role --role-name "$SCHEDULER_ROLE_NAME" \
      --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"scheduler.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
    aws iam put-role-policy --role-name "$SCHEDULER_ROLE_NAME" --policy-name invoke \
      --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"lambda:InvokeFunction\"],\"Resource\":\"${LAMBDA_ARN}\"}]}"
    sleep 5
  fi

  ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
  ENV_FILE="$(mktemp)"
  ENV_TMP="$ENV_FILE" EC2_LIST="$EC2_LIST" RDS_INSTANCE_ID="$RDS_INSTANCE_ID" AWS_REGION="$AWS_REGION" \
    python3 -c 'import json,os; json.dump({"Variables":{"SCHEDULE_REGION":os.environ["AWS_REGION"],"EC2_INSTANCE_IDS":os.environ["EC2_LIST"],"RDS_INSTANCE_ID":os.environ["RDS_INSTANCE_ID"]}}, open(os.environ["ENV_TMP"],"w"))'
  if aws lambda get-function --region "$AWS_REGION" --function-name "$FUNCTION_NAME" &>/dev/null; then
    aws lambda update-function-code --region "$AWS_REGION" --function-name "$FUNCTION_NAME" \
      --zip-file "fileb://${ZIP}" >/dev/null
    aws lambda wait function-updated --region "$AWS_REGION" --function-name "$FUNCTION_NAME"
    aws lambda update-function-configuration --region "$AWS_REGION" --function-name "$FUNCTION_NAME" \
      --timeout 900 --environment "file://${ENV_FILE}" >/dev/null
  else
    aws lambda create-function --region "$AWS_REGION" --function-name "$FUNCTION_NAME" \
      --runtime python3.11 --role "$ROLE_ARN" --handler schedule_handler.handler \
      --zip-file "fileb://${ZIP}" --timeout 900 --environment "file://${ENV_FILE}" >/dev/null
  fi
  rm -f "$ENV_FILE"

  aws lambda add-permission --region "$AWS_REGION" --function-name "$FUNCTION_NAME" \
    --statement-id scheduler-invoke --action lambda:InvokeFunction \
    --principal scheduler.amazonaws.com 2>/dev/null || true

  TARGET_START='{"Arn":"'"$LAMBDA_ARN"'","RoleArn":"'"$SCHED_ROLE_ARN"'","Input":"{\"action\":\"start\"}"}'
  TARGET_STOP='{"Arn":"'"$LAMBDA_ARN"'","RoleArn":"'"$SCHED_ROLE_ARN"'","Input":"{\"action\":\"stop\"}"}'

  aws scheduler delete-schedule --region "$AWS_REGION" --name "$START_SCHEDULE" 2>/dev/null || true
  aws scheduler create-schedule --region "$AWS_REGION" --name "$START_SCHEDULE" \
    --schedule-expression "$CRON_START" --schedule-expression-timezone UTC \
    --flexible-time-window Mode=OFF --target "$TARGET_START"

  aws scheduler delete-schedule --region "$AWS_REGION" --name "$STOP_SCHEDULE" 2>/dev/null || true
  aws scheduler create-schedule --region "$AWS_REGION" --name "$STOP_SCHEDULE" \
    --schedule-expression "$CRON_STOP" --schedule-expression-timezone UTC \
    --flexible-time-window Mode=OFF --target "$TARGET_STOP"

  log "Schedules created."
else
  log "DRY-RUN: would deploy Lambda + EventBridge Scheduler (8am/8pm IST)"
fi
