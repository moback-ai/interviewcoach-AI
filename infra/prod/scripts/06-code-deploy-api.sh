#!/usr/bin/env bash
# Phase 3 (Code) — Deploy API on prod EC2 (SSH + docker compose). Secrets-only env on host.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

SCRIPT_DIR="$(dirname "$0")"
SSH="$SCRIPT_DIR/ssh-prod.sh"
API_HOST="${API_HOST:?Set API_HOST in prod.env}"
ECR_REGISTRY="${ECR_REGISTRY:?Set ECR_REGISTRY in prod.env or env}"
IMAGE_TAG="${IMAGE_TAG:-prod-20260629}"
REGION="${AWS_REGION:-ap-south-1}"
COMPOSE_FILE="/apps/interviewcoach/docker/compose.prod.yml"

chmod +x "$SSH"
API_IP="${API_HOST#*@}"

"$SSH" "sudo mkdir -p /apps/interviewcoach/docker && cd /apps/interviewcoach"
"$SSH" --scp "$(dirname "$0")/../../../docker/compose.prod.yml" "${SSH_USER}@${API_IP}:/tmp/compose.prod.yml"

"$SSH" bash -s <<EOF
set -euo pipefail
aws ecr get-login-password --region ${REGION} | sudo docker login --username AWS --password-stdin ${ECR_REGISTRY}
sudo mkdir -p /apps/interviewcoach
sudo mv /tmp/compose.prod.yml ${COMPOSE_FILE}
cd /apps/interviewcoach
export ECR_REGISTRY=${ECR_REGISTRY}
export IMAGE_TAG=${IMAGE_TAG}
export AWS_REGION=${REGION}
sudo -E docker compose -f ${COMPOSE_FILE} pull
sudo -E docker compose -f ${COMPOSE_FILE} up -d
curl -fsS http://127.0.0.1:5000/api/health | head -c 500 || true
EOF

echo "Phase 3 step 6 complete. Check http://${API_IP}:5000/api/health"
