#!/usr/bin/env bash
# Verify API image tag exists in ECR before deploy rollout (no build on deploy).
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
ECR_REGISTRY="${ECR_REGISTRY:?Set ECR_REGISTRY}"
IMAGE_TAG="${IMAGE_TAG:?Set IMAGE_TAG}"
REPO_NAME="${ECR_API_REPO:-interviewcoach-api}"

if [[ ! "$IMAGE_TAG" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
  echo "ERROR: Invalid IMAGE_TAG '$IMAGE_TAG' (use letters, digits, ., _, - only)." >&2
  exit 1
fi

if aws ecr describe-images \
  --region "$REGION" \
  --repository-name "$REPO_NAME" \
  --image-ids "imageTag=${IMAGE_TAG}" >/dev/null 2>&1; then
  echo "ECR image ready: ${ECR_REGISTRY}/${REPO_NAME}:${IMAGE_TAG}"
  exit 0
fi

echo "ERROR: Image ${ECR_REGISTRY}/${REPO_NAME}:${IMAGE_TAG} not found in ECR." >&2
echo "Build once via devsecops-platform → InterviewCoach · Build Docker Images, then deploy with that tag." >&2
exit 1
