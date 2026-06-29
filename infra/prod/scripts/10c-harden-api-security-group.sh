#!/usr/bin/env bash
# Harden prod API security group: remove public :5000; optionally restrict SSH.
# CloudFront reaches the API via nginx on :80 only.
#
# Usage: bash infra/prod/scripts/10c-harden-api-security-group.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
INSTANCE_ID="${API_INSTANCE_ID:?Set API_INSTANCE_ID in prod.env}"
SSH_ALLOW_CIDR="${SSH_ALLOW_CIDR:-}"

SG_ID=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)

echo "API instance: $INSTANCE_ID"
echo "Security group: $SG_ID"

revoke_public_port() {
  local port="$1"
  if aws ec2 describe-security-groups --region "$REGION" --group-ids "$SG_ID" \
    --query "SecurityGroups[0].IpPermissions[?FromPort==\`$port\` && ToPort==\`$port\`]" \
    --output text | grep -q '0.0.0.0/0'; then
    aws ec2 revoke-security-group-ingress \
      --region "$REGION" \
      --group-id "$SG_ID" \
      --protocol tcp \
      --port "$port" \
      --cidr 0.0.0.0/0
    echo "Revoked public TCP $port"
  else
    echo "Public TCP $port already closed"
  fi
}

revoke_public_port 5000

if [[ -n "$SSH_ALLOW_CIDR" ]]; then
  echo "Restricting SSH to $SSH_ALLOW_CIDR ..."
  if aws ec2 describe-security-groups --region "$REGION" --group-ids "$SG_ID" \
    --query 'SecurityGroups[0].IpPermissions[?FromPort==`22`]' --output text | grep -q '0.0.0.0/0'; then
    aws ec2 revoke-security-group-ingress \
      --region "$REGION" \
      --group-id "$SG_ID" \
      --protocol tcp \
      --port 22 \
      --cidr 0.0.0.0/0
  fi
  if ! aws ec2 describe-security-groups --region "$REGION" --group-ids "$SG_ID" \
    --query "SecurityGroups[0].IpPermissions[?FromPort==\`22\`]" --output text | grep -q "$SSH_ALLOW_CIDR"; then
    aws ec2 authorize-security-group-ingress \
      --region "$REGION" \
      --group-id "$SG_ID" \
      --protocol tcp \
      --port 22 \
      --cidr "$SSH_ALLOW_CIDR"
    echo "SSH allowed from $SSH_ALLOW_CIDR"
  fi
else
  echo "SSH_ALLOW_CIDR unset — leaving SSH rules unchanged (set in prod.env to restrict)."
fi

echo "Security group hardening complete."
