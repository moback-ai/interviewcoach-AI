#!/usr/bin/env bash
# Weekday schedule (Mon–Fri): START 10:00 AM IST, STOP 7:30 PM IST
# Weekend (Sat–Sun): force STOP at 00:05 IST (safety — keeps all instances off)
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
SCHEDULE_TIMEZONE="${SCHEDULE_TIMEZONE:-Asia/Kolkata}"
SCHEDULE_START_IST="${SCHEDULE_START_IST:-10:00}"
SCHEDULE_STOP_IST="${SCHEDULE_STOP_IST:-19:30}"

START_H="${SCHEDULE_START_IST%%:*}"
START_M="${SCHEDULE_START_IST##*:}"
STOP_H="${SCHEDULE_STOP_IST%%:*}"
STOP_M="${SCHEDULE_STOP_IST##*:}"

START_SCHEDULE="${SCHEDULE_START_NAME:-interviewcoach-start-weekdays-10am-ist}"
STOP_WEEKDAY_SCHEDULE="${SCHEDULE_STOP_WEEKDAY_NAME:-interviewcoach-stop-weekdays-730pm-ist}"
STOP_SAT_SCHEDULE="${SCHEDULE_STOP_SAT_NAME:-interviewcoach-stop-weekend-sat}"
STOP_SUN_SCHEDULE="${SCHEDULE_STOP_SUN_NAME:-interviewcoach-stop-weekend-sun}"

CRON_START="cron(${START_M} ${START_H} ? * MON-FRI *)"
CRON_STOP_WEEKDAY="cron(${STOP_M} ${STOP_H} ? * MON-FRI *)"
CRON_STOP_SAT="cron(5 0 ? * SAT *)"
CRON_STOP_SUN="cron(5 0 ? * SUN *)"

LEGACY_SCHEDULES=(
  interviewcoach-start-10am-ist
  interviewcoach-stop-8pm-ist
)

API_ID="${API_INSTANCE_ID:-}"
if [[ -n "$API_ID" ]]; then
  EC2_LIST="${FRONTEND_INSTANCE_ID},${API_ID},${AI_INSTANCE_ID}"
else
  EC2_LIST="${FRONTEND_INSTANCE_ID},${AI_INSTANCE_ID}"
fi

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

upsert_schedule() {
  local name="$1"
  local cron="$2"
  local target_json="$3"
  if [[ "$APPLY" -eq 1 ]]; then
    aws scheduler delete-schedule --region "$AWS_REGION" --name "$name" 2>/dev/null || true
    aws scheduler create-schedule --region "$AWS_REGION" --name "$name" \
      --schedule-expression "$cron" \
      --schedule-expression-timezone "$SCHEDULE_TIMEZONE" \
      --flexible-time-window Mode=OFF \
      --target "$target_json"
    log "Schedule created: $name ($cron $SCHEDULE_TIMEZONE)"
  else
    log "DRY-RUN: schedule $name → $cron ($SCHEDULE_TIMEZONE)"
  fi
}

log "EC2: $EC2_LIST | RDS: $RDS_INSTANCE_ID"
log "Weekdays Mon–Fri: START ${SCHEDULE_START_IST} IST | STOP ${SCHEDULE_STOP_IST} IST"
log "Weekends Sat–Sun: STOP 00:05 IST (force off)"
log "Timezone: $SCHEDULE_TIMEZONE"

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

  for legacy in "${LEGACY_SCHEDULES[@]}"; do
    aws scheduler delete-schedule --region "$AWS_REGION" --name "$legacy" 2>/dev/null || true
    log "Removed legacy schedule (if existed): $legacy"
  done

  TARGET_START='{"Arn":"'"$LAMBDA_ARN"'","RoleArn":"'"$SCHED_ROLE_ARN"'","Input":"{\"action\":\"start\"}"}'
  TARGET_STOP='{"Arn":"'"$LAMBDA_ARN"'","RoleArn":"'"$SCHED_ROLE_ARN"'","Input":"{\"action\":\"stop\"}"}'

  upsert_schedule "$START_SCHEDULE" "$CRON_START" "$TARGET_START"
  upsert_schedule "$STOP_WEEKDAY_SCHEDULE" "$CRON_STOP_WEEKDAY" "$TARGET_STOP"
  upsert_schedule "$STOP_SAT_SCHEDULE" "$CRON_STOP_SAT" "$TARGET_STOP"
  upsert_schedule "$STOP_SUN_SCHEDULE" "$CRON_STOP_SUN" "$TARGET_STOP"

  log "All schedules applied."
else
  log "DRY-RUN: would deploy Lambda + 4 EventBridge schedules (Mon–Fri 10am–7:30pm IST, weekend force-stop)"
  upsert_schedule "$START_SCHEDULE" "$CRON_START" "(start target)"
  upsert_schedule "$STOP_WEEKDAY_SCHEDULE" "$CRON_STOP_WEEKDAY" "(stop target)"
  upsert_schedule "$STOP_SAT_SCHEDULE" "$CRON_STOP_SAT" "(stop target)"
  upsert_schedule "$STOP_SUN_SCHEDULE" "$CRON_STOP_SUN" "(stop target)"
fi
