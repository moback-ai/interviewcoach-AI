#!/usr/bin/env bash
# Phase 1 (AWS) — Attach prod API policy to EC2 instance role (Secrets + Bedrock + S3 + Transcribe).
# Usage: INSTANCE_ROLE_NAME=interviewcoach-api-role bash 04-aws-iam-attach.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
INSTANCE_ROLE_NAME="${INSTANCE_ROLE_NAME:-InterviewCoachBackendSecretsRole}"
POLICY_NAME="${POLICY_NAME:-InterviewCoachProdApi}"
POLICY_FILE="${POLICY_FILE:-$(dirname "$0")/../iam/api-task-role-policy.json}"

if [[ ! -f "$POLICY_FILE" ]]; then
  echo "Missing policy file: $POLICY_FILE"
  exit 1
fi

POLICY_ARN=$(aws iam list-policies --scope Local --query "Policies[?PolicyName=='${POLICY_NAME}'].Arn" --output text)
if [[ -z "$POLICY_ARN" || "$POLICY_ARN" == "None" ]]; then
  echo "Creating IAM policy $POLICY_NAME ..."
  POLICY_ARN=$(aws iam create-policy \
    --policy-name "$POLICY_NAME" \
    --policy-document "file://${POLICY_FILE}" \
    --query Policy.Arn --output text)
else
  echo "Updating IAM policy $POLICY_NAME ..."
  aws iam create-policy-version \
    --policy-arn "$POLICY_ARN" \
    --policy-document "file://${POLICY_FILE}" \
    --set-as-default >/dev/null
fi

echo "Attaching $POLICY_ARN to role $INSTANCE_ROLE_NAME ..."
aws iam attach-role-policy \
  --role-name "$INSTANCE_ROLE_NAME" \
  --policy-arn "$POLICY_ARN"

echo "Phase 1 step 4 complete. API instances can read Secrets Manager and call Bedrock."
