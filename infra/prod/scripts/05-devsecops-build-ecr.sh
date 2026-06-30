#!/usr/bin/env bash
# Build PROD API image and push to ECR — devsecops-platform GitHub Actions only.
# Skips build/push when the tag already exists in ECR (deploy-only). Set FORCE_REBUILD=1 to rebuild.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
REGION="${AWS_REGION:-ap-south-1}"
ECR_REGISTRY="${ECR_REGISTRY:?Set ECR_REGISTRY in prod.env or env}"
IMAGE_TAG="${IMAGE_TAG:?Set IMAGE_TAG}"
REPO_NAME="${ECR_API_REPO:-interviewcoach-api}"
REPO="${ECR_REGISTRY}/${REPO_NAME}"

image_exists_in_ecr() {
  aws ecr describe-images \
    --region "$REGION" \
    --repository-name "$REPO_NAME" \
    --image-ids "imageTag=${IMAGE_TAG}" \
    >/dev/null 2>&1
}

if [[ "${FORCE_REBUILD:-}" != "1" ]] && image_exists_in_ecr; then
  echo "Image ${REPO}:${IMAGE_TAG} already in ECR — skipping build (set FORCE_REBUILD=1 to rebuild)."
  exit 0
fi

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker build -f "$ROOT/docker/api/Dockerfile.prod" -t "${REPO}:${IMAGE_TAG}" "$ROOT"
docker push "${REPO}:${IMAGE_TAG}"

echo "Pushed ${REPO}:${IMAGE_TAG}"
