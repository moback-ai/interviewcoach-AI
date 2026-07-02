#!/usr/bin/env bash
# Roll back API ASG to a previous ECR image tag.
# Usage: IMAGE_TAG=prod-20260701-abc1234 bash infra/prod/scripts/07b-rollback-api-asg.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_TAG="${IMAGE_TAG:?Set IMAGE_TAG to the previous ECR tag}"

echo "Rolling back API to ${IMAGE_TAG} ..."
bash "${SCRIPT_DIR}/06-code-deploy-api-asg.sh"
bash "${SCRIPT_DIR}/07-smoke-test-prod.sh"
