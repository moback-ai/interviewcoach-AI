#!/usr/bin/env bash
# Delete unused ACM certificates stuck in PENDING_VALIDATION (keeps issued cert in prod.env).
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

CF_REGION="us-east-1"
KEEP_ARN="${ACM_CERT_ARN:?Set ACM_CERT_ARN in prod.env}"
APEX="${APEX_DOMAIN:-ugaanlabs.ai}"

echo "Keeping issued cert: $KEEP_ARN"

mapfile -t PENDING < <(aws acm list-certificates --region "$CF_REGION" \
  --certificate-statuses PENDING_VALIDATION \
  --query "CertificateSummaryList[?DomainName=='${APEX}'].CertificateArn" --output text | tr '\t' '\n')

if [[ ${#PENDING[@]} -eq 0 || -z "${PENDING[0]}" ]]; then
  echo "No pending ACM certs for ${APEX}."
  exit 0
fi

for arn in "${PENDING[@]}"; do
  [[ -z "$arn" || "$arn" == "None" ]] && continue
  if [[ "$arn" == "$KEEP_ARN" ]]; then
    echo "Skip keep: $arn"
    continue
  fi
  echo "Deleting pending cert: $arn"
  aws acm delete-certificate --region "$CF_REGION" --certificate-arn "$arn"
done

echo "ACM cleanup complete."
