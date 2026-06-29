#!/usr/bin/env bash
# Terminate Plan B EC2 hosts (API + AI + frontend) and launch one fresh prod API instance.
# Usage: CONFIRM=YES bash infra/prod/scripts/11-aws-fresh-ec2.sh
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

REGION="${AWS_REGION:-ap-south-1}"
EC2_STACK_NAME="${EC2_STACK_NAME:-interviewcoach-prod-api}"
TEMPLATE="${TEMPLATE:-$(dirname "$0")/../cloudformation/prod-ec2-stack.yaml}"
VPC_ID="${VPC_ID:-vpc-02d05a1b90499b22d}"
SUBNET_ID="${SUBNET_ID:-subnet-00662d4d6964a6ee4}"
KEY_NAME="${KEY_NAME:-interviewcoach-key-v2}"
AMI_ID="${AMI_ID:-ami-0a1b0c508e1fa9fce}"
INSTANCE_TYPE="${INSTANCE_TYPE:-c6i.large}"
SSH_USER="${SSH_USER:-ubuntu}"

OLD_IDS=(
  "${API_INSTANCE_ID:-i-084ba7dcceefd1636}"
  "${AI_INSTANCE_ID:-i-032833ba1cbb49b9b}"
  "${FRONTEND_INSTANCE_ID:-i-0d8d448bff2dceb87}"
)

if [[ "${CONFIRM:-}" != "YES" ]]; then
  echo "This will TERMINATE all Plan B EC2 instances and release their Elastic IPs."
  echo "Old instances: ${OLD_IDS[*]}"
  echo "Re-run with: CONFIRM=YES bash $0"
  exit 1
fi

echo "=== Step 0: Backup Secrets Manager ==="
bash "$(dirname "$0")/00-backup-secrets.sh"

echo "=== Step 1: Terminate old EC2 instances ==="
aws ec2 terminate-instances --region "$REGION" --instance-ids "${OLD_IDS[@]}"
echo "Waiting for instances to terminate ..."
aws ec2 wait instance-terminated --region "$REGION" --instance-ids "${OLD_IDS[@]}"

echo "=== Step 2: Release old Elastic IPs ==="
while read -r alloc assoc; do
  [[ -z "$alloc" || "$alloc" == "None" ]] && continue
  if [[ -n "$assoc" && "$assoc" != "None" ]]; then
    aws ec2 disassociate-address --region "$REGION" --association-id "$assoc" || true
  fi
  aws ec2 release-address --region "$REGION" --allocation-id "$alloc" || true
done < <(aws ec2 describe-addresses --region "$REGION" \
  --query 'Addresses[].[AllocationId,AssociationId]' --output text)

echo "=== Step 3: Deploy fresh API EC2 (CloudFormation) ==="
if aws cloudformation describe-stacks --region "$REGION" --stack-name "$EC2_STACK_NAME" >/dev/null 2>&1; then
  echo "Stack $EC2_STACK_NAME already exists — updating ..."
fi
aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$EC2_STACK_NAME" \
  --template-file "$TEMPLATE" \
  --parameter-overrides \
    VpcId="$VPC_ID" \
    SubnetId="$SUBNET_ID" \
    KeyName="$KEY_NAME" \
    AmiId="$AMI_ID" \
    InstanceType="$INSTANCE_TYPE" \
    InstanceProfileName="${INSTANCE_PROFILE_NAME:-InterviewCoachBackendSecretsProfile}" \
  --capabilities CAPABILITY_NAMED_IAM

INSTANCE_ID=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$EC2_STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text)
PUBLIC_IP=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$EC2_STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='PublicIp'].OutputValue" --output text)
PRIVATE_IP=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$EC2_STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='PrivateIp'].OutputValue" --output text)

echo "=== Step 4: Wait for SSH (${SSH_USER}@${PUBLIC_IP}) ==="
SSH_SCRIPT="$(dirname "$0")/ssh-prod.sh"
chmod +x "$SSH_SCRIPT"
export API_PUBLIC_IP="$PUBLIC_IP"
for _ in $(seq 1 30); do
  if "$SSH_SCRIPT" "echo ok" 2>/dev/null; then
    echo "SSH ready."
    break
  fi
  sleep 10
done

echo "=== Step 5: Update prod.env ==="
PROD_ENV="$(dirname "$0")/../prod.env"
python3 - "$PROD_ENV" "$INSTANCE_ID" "$PUBLIC_IP" "$PRIVATE_IP" "$SSH_USER" <<'PY'
import re, sys
path, iid, pub, priv, user = sys.argv[1:6]
lines = open(path).read().splitlines()
skip_keys = {"AI_HOST", "AI_INSTANCE_ID", "FRONTEND_HOST", "FRONTEND_INSTANCE_ID"}
updates = {
    "API_INSTANCE_ID": iid,
    "API_PUBLIC_IP": pub,
    "API_PRIVATE_IP": priv,
    "API_HOST": f"{user}@{pub}",
    "SSH_USER": user,
    "EC2_STACK_NAME": "interviewcoach-prod-api",
}
out = []
seen = set()
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line and not line.strip().startswith("#") else ""
    if key in skip_keys:
        continue
    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, val in updates.items():
    if key not in seen:
        out.append(f"{key}={val}")
open(path, "w").write("\n".join(out) + "\n")
PY

echo "=== Step 6: Patch Secrets Manager ==="
SECRET_TMP=$(mktemp)
aws secretsmanager get-secret-value --region "$REGION" \
  --secret-id "${SECRET_ID:-interviewcoach/prod/app}" \
  --query SecretString --output text > "$SECRET_TMP"
python3 - "$SECRET_TMP" "$INSTANCE_ID" "$PUBLIC_IP" "$PRIVATE_IP" "$SSH_USER" <<'PY'
import json, sys
path, iid, pub, priv, user = sys.argv[1:6]
d = json.load(open(path))
d.update({
    "API_INSTANCE_ID": iid,
    "API_PUBLIC_IP": pub,
    "API_PRIVATE_IP": priv,
    "BACKEND_HOST": pub,
    "EC2_USER": user,
    "INFRA_LAYOUT": "single-api",
})
for k in [
    "AI_HOST", "AI_INSTANCE_ID", "AI_PUBLIC_IP", "AI_PRIVATE_IP",
    "FRONTEND_HOST", "FRONTEND_INSTANCE_ID", "FRONTEND_PUBLIC_IP", "FRONTEND_PRIVATE_IP",
    "OLLAMA_HOST", "OLLAMA_HEALTH_URL", "TRANSCRIBE_SERVICE_URL",
]:
    d.pop(k, None)
json.dump(d, open(path, "w"), indent=2)
open(path, "a").write("\n")
PY
aws secretsmanager put-secret-value \
  --region "$REGION" \
  --secret-id "${SECRET_ID:-interviewcoach/prod/app}" \
  --secret-string "file://${SECRET_TMP}"
rm -f "$SECRET_TMP"

echo ""
echo "=== Fresh prod API ready ==="
echo "  Instance: $INSTANCE_ID"
echo "  Public IP:  $PUBLIC_IP  (new — old IPs released)"
echo "  SSH:        ${SSH_USER}@${PUBLIC_IP}"
echo ""
echo "Next:"
echo "  bash infra/prod/scripts/05-devsecops-build-ecr.sh"
echo "  bash infra/prod/scripts/06-code-deploy-api.sh"
