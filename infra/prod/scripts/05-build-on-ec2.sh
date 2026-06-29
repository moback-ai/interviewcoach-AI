#!/usr/bin/env bash
# Build PROD API image on the EC2 host (when local Docker is unavailable) and push to ECR.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SSH="$(dirname "$0")/ssh-prod.sh"
REGION="${AWS_REGION:-ap-south-1}"
ECR_REGISTRY="${ECR_REGISTRY:?Set ECR_REGISTRY}"
IMAGE_TAG="${IMAGE_TAG:-prod-20260629}"
REPO="${ECR_REGISTRY}/${ECR_API_REPO:-interviewcoach-api}"

chmod +x "$SSH"
bash "$(dirname "$0")/04-aws-iam-attach.sh" >/dev/null 2>&1 || true

echo "Packaging build context (streaming to EC2) ..."
API_IP="${API_PUBLIC_IP:-${API_HOST#*@}}"

tar czf - \
  -C "$ROOT" \
  --exclude='backend/venv' \
  --exclude='backend/__pycache__' \
  --exclude='backend/.secrets-backup' \
  --exclude='backend/Piper/*.onnx' \
  --exclude='frontend' \
  --exclude='node_modules' \
  --exclude='.git' \
  backend docker/api/Dockerfile.prod \
  | "$SSH" "mkdir -p /tmp/ic-api-build && tar xzf - -C /tmp/ic-api-build"

if [[ -f "$ROOT/backend/Piper/en_US-kusal-medium.onnx" ]]; then
  echo "Uploading Piper model ..."
  aws s3 cp "$ROOT/backend/Piper/en_US-kusal-medium.onnx" \
    "s3://${USER_FILES_BUCKET}/build/piper-model.onnx" --region "$REGION"
  "$SSH" "mkdir -p /tmp/ic-api-build/backend/Piper && aws s3 cp s3://${USER_FILES_BUCKET}/build/piper-model.onnx /tmp/ic-api-build/backend/Piper/en_US-kusal-medium.onnx --region ${REGION}"
fi

echo "Building and pushing on EC2 ..."
"$SSH" bash -s <<EOF
set -euo pipefail
cd /tmp/ic-api-build
aws ecr get-login-password --region ${REGION} | sudo docker login --username AWS --password-stdin ${ECR_REGISTRY}
sudo docker build -f docker/api/Dockerfile.prod -t ${REPO}:${IMAGE_TAG} .
sudo docker push ${REPO}:${IMAGE_TAG}
echo "Pushed ${REPO}:${IMAGE_TAG}"
EOF

echo "Phase 2 build-on-EC2 complete."
