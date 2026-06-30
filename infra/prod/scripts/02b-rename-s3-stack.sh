#!/usr/bin/env bash
# Rename CloudFormation stack interviewcoach-prod-hybrid-s3 → interviewcoach-prod-s3
# (retain existing S3 buckets, import into new stack name). PROD only.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
OLD_STACK="${OLD_S3_STACK_NAME:-interviewcoach-prod-hybrid-s3}"
NEW_STACK="${STACK_NAME:-interviewcoach-prod-s3}"
TEMPLATE="$(dirname "$0")/../cloudformation/prod-stack.yaml"
STATIC_BUCKET="${STATIC_BUCKET:-ic-static-prod}"
USER_FILES_BUCKET="${USER_FILES_BUCKET:-ic-user-files-prod}"
IMPORT_JSON="$(mktemp)"
trap 'rm -f "$IMPORT_JSON"' EXIT

if aws cloudformation describe-stacks --region "$REGION" --stack-name "$NEW_STACK" >/dev/null 2>&1; then
  echo "Stack $NEW_STACK already exists — nothing to rename."
  exit 0
fi

if aws cloudformation describe-stacks --region "$REGION" --stack-name "$OLD_STACK" >/dev/null 2>&1; then
  echo "Updating $OLD_STACK with Retain policy on buckets ..."
  aws cloudformation deploy \
    --region "$REGION" \
    --stack-name "$OLD_STACK" \
    --template-file "$TEMPLATE" \
    --parameter-overrides \
      StaticBucketName="$STATIC_BUCKET" \
      UserFilesBucketName="$USER_FILES_BUCKET" \
    --no-fail-on-empty-changeset

  echo "Deleting $OLD_STACK (buckets retained via DeletionPolicy) ..."
  aws cloudformation delete-stack --region "$REGION" --stack-name "$OLD_STACK"
  aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$OLD_STACK"
  echo "Old stack deleted; buckets retained."
else
  echo "Old stack $OLD_STACK not found — importing buckets into $NEW_STACK."
fi

if ! aws s3api head-bucket --bucket "$STATIC_BUCKET" --region "$REGION" 2>/dev/null; then
  echo "Bucket $STATIC_BUCKET missing — deploying fresh stack."
  bash "$(dirname "$0")/02-aws-cloudformation.sh"
  exit 0
fi

cat > "$IMPORT_JSON" <<EOF
[
  {
    "ResourceType": "AWS::S3::Bucket",
    "LogicalResourceId": "StaticBucket",
    "ResourceIdentifier": {
      "BucketName": "${STATIC_BUCKET}"
    }
  },
  {
    "ResourceType": "AWS::S3::Bucket",
    "LogicalResourceId": "UserFilesBucket",
    "ResourceIdentifier": {
      "BucketName": "${USER_FILES_BUCKET}"
    }
  }
]
EOF

CHANGE_SET="import-${NEW_STACK}-$(date +%s)"
IMPORT_TEMPLATE="$(dirname "$0")/../cloudformation/prod-stack-import.yaml"
aws cloudformation create-change-set \
  --region "$REGION" \
  --stack-name "$NEW_STACK" \
  --change-set-name "$CHANGE_SET" \
  --change-set-type IMPORT \
  --resources-to-import "file://${IMPORT_JSON}" \
  --template-body "file://${IMPORT_TEMPLATE}" \
  --parameters \
    "ParameterKey=StaticBucketName,ParameterValue=${STATIC_BUCKET}" \
    "ParameterKey=UserFilesBucketName,ParameterValue=${USER_FILES_BUCKET}" \
  --capabilities CAPABILITY_IAM

aws cloudformation wait change-set-create-complete \
  --region "$REGION" \
  --stack-name "$NEW_STACK" \
  --change-set-name "$CHANGE_SET"

aws cloudformation execute-change-set \
  --region "$REGION" \
  --stack-name "$NEW_STACK" \
  --change-set-name "$CHANGE_SET"

aws cloudformation wait stack-import-complete --region "$REGION" --stack-name "$NEW_STACK"

echo "Import complete — applying full template with outputs ..."
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$NEW_STACK" \
  --template-file "$TEMPLATE" \
  --parameter-overrides \
    StaticBucketName="$STATIC_BUCKET" \
    UserFilesBucketName="$USER_FILES_BUCKET" \
  --no-fail-on-empty-changeset

echo "Stack renamed: $OLD_STACK → $NEW_STACK"
