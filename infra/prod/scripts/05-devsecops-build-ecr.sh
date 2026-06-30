#!/usr/bin/env bash
# Build PROD API image and push to ECR — GitHub Actions ONLY.
# Local/Mac/EC2 builds are blocked. Use: .github/workflows/deploy-prod.yml
set -euo pipefail

if [[ "${GITHUB_ACTIONS:-}" != "true" ]]; then
  echo "ERROR: Prod API images are built only on GitHub Actions."
  echo "  Actions → Deploy PROD → Run workflow"
  echo "  https://github.com/moback-ai/interviewcoach-AI/actions/workflows/deploy-prod.yml"
  exit 1
fi

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
