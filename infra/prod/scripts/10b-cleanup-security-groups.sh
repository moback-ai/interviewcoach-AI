#!/usr/bin/env bash
# Remove Plan B security group rules and unused SGs (no EC2 attached).
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
BACKEND_SG="${PLAN_B_BACKEND_SG:-sg-0f83e275411e1a397}"
FRONTEND_SG="${PLAN_B_FRONTEND_SG:-sg-02d77877092e85c35}"
AI_PRIVATE_IP="${PLAN_B_AI_PRIVATE_IP:-172.31.36.78/32}"

revoke() {
  local port="$1"
  aws ec2 revoke-security-group-ingress \
    --region "$REGION" \
    --group-id "$BACKEND_SG" \
    --protocol tcp \
    --port "$port" \
    --cidr "$AI_PRIVATE_IP" 2>/dev/null && echo "Revoked ingress $port from $BACKEND_SG" || echo "Skip $port (already removed)"
}

revoke 11434
revoke 5001

for sg in "$BACKEND_SG" "$FRONTEND_SG"; do
  attached=$(aws ec2 describe-network-interfaces --region "$REGION" \
    --filters "Name=group-id,Values=$sg" \
    --query 'length(NetworkInterfaces)' --output text)
  if [[ "$attached" == "0" ]]; then
    aws ec2 delete-security-group --region "$REGION" --group-id "$sg" 2>/dev/null \
      && echo "Deleted unused SG $sg" || echo "Could not delete SG $sg"
  else
    echo "SG $sg still attached — not deleted"
  fi
done

echo "Security group cleanup complete."
