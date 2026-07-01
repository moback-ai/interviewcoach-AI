#!/usr/bin/env bash
# Build PROD API image and push to ECR — devsecops-platform GitHub Actions only.
# Skips build/push when the tag already exists in ECR (deploy-only). Set FORCE_REBUILD=1 to rebuild.
# Set REBUILD_DEPS=1 to rebuild interviewcoach-api:deps-latest (when requirements.prod.txt changes).
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
DEPS_TAG="${DEPS_IMAGE_TAG:-deps-latest}"

ecr_tag_exists() {
  local tag="$1"
  aws ecr describe-images \
    --region "$REGION" \
    --repository-name "$REPO_NAME" \
    --image-ids "imageTag=${tag}" \
    >/dev/null 2>&1
}

if [[ "${FORCE_REBUILD:-}" != "1" ]] && ecr_tag_exists "$IMAGE_TAG"; then
  echo "Image ${REPO}:${IMAGE_TAG} already in ECR — skipping build (set FORCE_REBUILD=1 to rebuild)."
  exit 0
fi

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

if [[ "${REBUILD_DEPS:-}" == "1" ]] || ! ecr_tag_exists "$DEPS_TAG"; then
  echo "Building deps base ${REPO}:${DEPS_TAG} ..."
  docker build -f "$ROOT/docker/api/Dockerfile.deps" -t "${REPO}:${DEPS_TAG}" "$ROOT"
  docker push "${REPO}:${DEPS_TAG}"
else
  echo "Reusing deps base ${REPO}:${DEPS_TAG}"
fi

echo "Building app image ${REPO}:${IMAGE_TAG} ..."
docker build -f "$ROOT/docker/api/Dockerfile.prod" \
  --build-arg "DEPS_IMAGE=${REPO}:${DEPS_TAG}" \
  -t "${REPO}:${IMAGE_TAG}" \
  "$ROOT"
docker push "${REPO}:${IMAGE_TAG}"

echo "Pushed ${REPO}:${IMAGE_TAG} (deps: ${DEPS_TAG})"
