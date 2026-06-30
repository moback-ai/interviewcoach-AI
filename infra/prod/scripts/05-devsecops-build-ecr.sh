#!/usr/bin/env bash
# Build PROD API image and push to ECR — devsecops-platform GitHub Actions only.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
REGION="${AWS_REGION:-ap-south-1}"
ECR_REGISTRY="${ECR_REGISTRY:?Set ECR_REGISTRY in prod.env or env}"
IMAGE_TAG="${IMAGE_TAG:?Set IMAGE_TAG}"
REPO="${ECR_REGISTRY}/${ECR_API_REPO:-interviewcoach-api}"

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker build -f "$ROOT/docker/api/Dockerfile.prod" -t "${REPO}:${IMAGE_TAG}" "$ROOT"
docker push "${REPO}:${IMAGE_TAG}"

echo "Pushed ${REPO}:${IMAGE_TAG}"
