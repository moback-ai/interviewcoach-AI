#!/usr/bin/env bash
# Plan B infrastructure setup (~$550/mo target) for InterviewCoach
#
# Usage:
#   ./plan-b-setup.sh              # dry-run (shows what would happen)
#   ./plan-b-setup.sh --apply      # execute RDS + frontend resize + SG rules
#   ./plan-b-setup.sh --apply --split-api   # also launch dedicated API EC2
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.env
source "${SCRIPT_DIR}/config.env"

APPLY=0
SPLIT_API=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --split-api) SPLIT_API=1; CREATE_API_INSTANCE="true" ;;
    -h|--help)
      sed -n '1,12p' "$0"
      exit 0
      ;;
  esac
done

log() { printf '\n[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
run() {
  if [[ "$APPLY" -eq 1 ]]; then
    log "RUN: $*"
    eval "$@"
  else
    log "DRY-RUN: $*"
  fi
}

require_aws() {
  aws sts get-caller-identity --region "$AWS_REGION" >/dev/null
}

wait_instance_stopped() {
  local id="$1"
  log "Waiting for $id to stop..."
  if [[ "$APPLY" -eq 1 ]]; then
    aws ec2 wait instance-stopped --region "$AWS_REGION" --instance-ids "$id"
  fi
}

wait_instance_running() {
  local id="$1"
  log "Waiting for $id to run..."
  if [[ "$APPLY" -eq 1 ]]; then
    aws ec2 wait instance-running --region "$AWS_REGION" --instance-ids "$id"
  fi
}

phase_rds_upgrade() {
  log "Phase 1: RDS ${RDS_INSTANCE_ID} -> ${TARGET_DB_CLASS}"
  local current
  current="$(aws rds describe-db-instances \
    --region "$AWS_REGION" \
    --db-instance-identifier "$RDS_INSTANCE_ID" \
    --query 'DBInstances[0].DBInstanceClass' \
    --output text)"
  log "Current DB class: $current"
  if [[ "$current" == "$TARGET_DB_CLASS" ]]; then
    log "RDS already on ${TARGET_DB_CLASS}; skip."
    return
  fi
  run aws rds modify-db-instance \
    --region "$AWS_REGION" \
    --db-instance-identifier "$RDS_INSTANCE_ID" \
    --db-instance-class "$TARGET_DB_CLASS" \
    --apply-immediately
}

phase_frontend_resize() {
  log "Phase 2: Frontend ${FRONTEND_INSTANCE_ID} -> ${TARGET_FRONTEND_TYPE}"
  local current
  current="$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --instance-ids "$FRONTEND_INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].InstanceType' \
    --output text)"
  log "Current frontend type: $current"
  if [[ "$current" == "$TARGET_FRONTEND_TYPE" ]]; then
    log "Frontend already ${TARGET_FRONTEND_TYPE}; skip."
    return
  fi
  log "WARNING: Site will be down for a few minutes during frontend resize."
  run aws ec2 stop-instances --region "$AWS_REGION" --instance-ids "$FRONTEND_INSTANCE_ID"
  if [[ "$APPLY" -eq 1 ]]; then
    wait_instance_stopped "$FRONTEND_INSTANCE_ID"
  fi
  run aws ec2 modify-instance-attribute \
    --region "$AWS_REGION" \
    --instance-id "$FRONTEND_INSTANCE_ID" \
    --instance-type "Value=${TARGET_FRONTEND_TYPE}"
  run aws ec2 start-instances --region "$AWS_REGION" --instance-ids "$FRONTEND_INSTANCE_ID"
  if [[ "$APPLY" -eq 1 ]]; then
    wait_instance_running "$FRONTEND_INSTANCE_ID"
  fi
}

phase_security_groups() {
  log "Phase 3: Security group rules (API <-> AI)"
  # Allow API port 5000 from frontend SG to AI/backend SG (current combined host)
  run aws ec2 authorize-security-group-ingress \
    --region "$AWS_REGION" \
    --group-id "$AI_SG_ID" \
    --protocol tcp \
    --port 5000 \
    --source-group "$FRONTEND_SG_ID" 2>/dev/null || log "Rule 5000 from frontend may already exist"

  if [[ "$SPLIT_API" -eq 1 ]]; then
    log "Split-API mode: allow Ollama 11434 only from API SG (after API instance exists)"
    log "Run update-nginx.sh after API EIP is known."
  fi
}

phase_launch_api_instance() {
  if [[ "$CREATE_API_INSTANCE" != "true" && "$SPLIT_API" -ne 1 ]]; then
    return
  fi
  log "Phase 4: Launch API instance ${TARGET_API_TYPE}"
  local existing
  existing="$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --filters "Name=tag:Name,Values=${API_INSTANCE_NAME}" "Name=instance-state-name,Values=running,stopped,pending" \
    --query 'Reservations[0].Instances[0].InstanceId' \
    --output text 2>/dev/null || true)"
  if [[ -n "$existing" && "$existing" != "None" ]]; then
    log "API instance already exists: $existing"
    echo "export API_INSTANCE_ID=$existing" >> "${SCRIPT_DIR}/outputs.env"
    return
  fi

  local user_data
  user_data="#!/bin/bash
set -e
apt-get update -y
apt-get install -y python3-pip python3-venv git nginx
"

  if [[ "$APPLY" -eq 1 ]]; then
    local instance_id
    instance_id="$(aws ec2 run-instances \
      --region "$AWS_REGION" \
      --image-id "$AMI_ID" \
      --instance-type "$TARGET_API_TYPE" \
      --key-name "$KEY_NAME" \
      --subnet-id "$AI_SUBNET_ID" \
      --security-group-ids "$AI_SG_ID" \
      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${API_INSTANCE_NAME}}]" \
      --iam-instance-profile Name=InterviewCoachBackendSecretsProfile \
      --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
      --user-data "$user_data" \
      --query 'Instances[0].InstanceId' \
      --output text)"
    log "Launched API instance: $instance_id"
    aws ec2 wait instance-running --region "$AWS_REGION" --instance-ids "$instance_id"
    local api_private api_public
    api_private="$(aws ec2 describe-instances --region "$AWS_REGION" --instance-ids "$instance_id" --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)"
    local alloc
    alloc="$(aws ec2 allocate-address --region "$AWS_REGION" --domain vpc --query AllocationId --output text)"
    aws ec2 associate-address --region "$AWS_REGION" --instance-id "$instance_id" --allocation-id "$alloc"
    api_public="$(aws ec2 describe-addresses --region "$AWS_REGION" --allocation-ids "$alloc" --query 'Addresses[0].PublicIp' --output text)"
    cat > "${SCRIPT_DIR}/outputs.env" <<EOF
export API_INSTANCE_ID="${instance_id}"
export API_PUBLIC_IP="${api_public}"
export API_PRIVATE_IP="${api_private}"
export OLLAMA_HOST="http://${AI_PRIVATE_IP}:11434"
export OLLAMA_HEALTH_URL="http://${AI_PRIVATE_IP}:11434/api/tags"
EOF
    log "Wrote ${SCRIPT_DIR}/outputs.env"
    # Ollama only from API private IP
    aws ec2 authorize-security-group-ingress \
      --region "$AWS_REGION" \
      --group-id "$AI_SG_ID" \
      --protocol tcp \
      --port 11434 \
      --cidr "${api_private}/32" 2>/dev/null || true
  else
    log "DRY-RUN: would launch ${TARGET_API_TYPE} in ${AI_SUBNET_ID} with EIP"
  fi
}

print_next_steps() {
  cat <<EOF

================================================================================
Plan B setup $([[ "$APPLY" -eq 1 ]] && echo "APPLIED" || echo "DRY-RUN COMPLETE")
================================================================================
Monthly estimate (on-demand):
  Frontend ${TARGET_FRONTEND_TYPE}     ~\$15
  AI ${AI_INSTANCE_ID} (c6i.2xlarge)  ~\$248  (Ollama)
  API ${TARGET_API_TYPE}              ~\$62   (if --split-api)
  RDS ${TARGET_DB_CLASS}              ~\$52
  Misc EBS/transfer                   ~\$30
  Total (split-api):                  ~\$430-500 / month

--- SSH tuning on AI/API host (13.200.28.73 until split) ---
  ssh -i ~/.ssh/interviewcoach-deploy.pem ubuntu@${AI_PUBLIC_IP}
  bash scripts/server-repair.sh
  # Append to app .env:
  QUESTION_GEN_FORCE_LOCAL=true
  JD_PARSE_USE_OLLAMA=false
  INTERVIEW_SERVER_TTS=false
  INTERVIEW_RESPONSE_TIMEOUT_SECONDS=45
  OLLAMA_MODEL=${OLLAMA_MODEL}
  $( [[ -f "${SCRIPT_DIR}/outputs.env" ]] && cat "${SCRIPT_DIR}/outputs.env" | grep OLLAMA || true )
  pm2 restart backend

--- After --split-api ---
  1. Deploy backend to API_INSTANCE (GitHub Manual Deploy -> new host)
  2. Run: ./update-frontend-nginx.sh --apply
  3. On AI host: pm2 stop backend (Ollama only)

--- Verify ---
  curl -s https://ugaanlabs.ai/api/health | python3 -m json.tool

Re-run without --apply to preview changes.
================================================================================
EOF
}

main() {
  require_aws
  log "Account: $(aws sts get-caller-identity --query Account --output text) Region: $AWS_REGION"
  [[ "$APPLY" -eq 0 ]] && log "DRY-RUN mode (pass --apply to execute)"
  phase_rds_upgrade
  phase_frontend_resize
  phase_security_groups
  phase_launch_api_instance
  print_next_steps
}

main "$@"
