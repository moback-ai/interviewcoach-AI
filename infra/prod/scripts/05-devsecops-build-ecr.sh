#!/usr/bin/env bash
# Phase 2 (DevSecOps ONLY) — Build PROD API image and push to ECR.
# Run via GitHub Actions: infra/prod/github-workflows/deploy-prod.yml
# Do NOT use 05-build-on-ec2.sh for prod.
# Usage: ECR_REGISTRY=123456789.dkr.ecr.ap-south-1.amazonaws.com IMAGE_TAG=prod-YYYYMMDD ./05-devsecops-build-ecr.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
REGION="${AWS_REGION:-ap-south-1}"
ECR_REGISTRY="${ECR_REGISTRY:?Set ECR_REGISTRY in prod.env or env}"
IMAGE_TAG="${IMAGE_TAG:-prod-20260629}"
REPO="${ECR_REGISTRY}/${ECR_API_REPO:-interviewcoach-api}"

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker build -f "$ROOT/docker/api/Dockerfile.prod" -t "${REPO}:${IMAGE_TAG}" "$ROOT"
docker push "${REPO}:${IMAGE_TAG}"

echo "Pushed ${REPO}:${IMAGE_TAG}"
echo "Phase 2 step 5 complete."
