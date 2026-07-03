#!/usr/bin/env bash
# Point CloudFront ApiOrigin at the prod ALB (required after ASG deploy; CFN may still reference old EC2).
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"
# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"

CF_DIST_ID="${CF_DIST_ID:?Set CF_DIST_ID}"
ALB_DNS="${ALB_DNS_NAME:?Set ALB_DNS_NAME}"

CURRENT=$(aws cloudfront get-distribution-config --id "$CF_DIST_ID" \
  --query "DistributionConfig.Origins.Items[?Id=='ApiOrigin'].DomainName | [0]" --output text)
if [[ "$CURRENT" == "$ALB_DNS" ]]; then
  echo "CloudFront ApiOrigin already $ALB_DNS"
  exit 0
fi

echo "CloudFront ApiOrigin: $CURRENT -> $ALB_DNS"
ETAG=$(aws cloudfront get-distribution-config --id "$CF_DIST_ID" --query ETag --output text)
DIST_TMP=$(mktemp)
trap 'rm -f "$DIST_TMP"' EXIT
aws cloudfront get-distribution-config --id "$CF_DIST_ID" --query DistributionConfig --output json > "$DIST_TMP"
python3 - "$DIST_TMP" "$ALB_DNS" <<'PY'
import json, os, sys
path, alb = sys.argv[1:3]
cfg = json.load(open(path))
for origin in cfg.get("Origins", {}).get("Items", []):
    if origin.get("Id") == "ApiOrigin":
        origin["DomainName"] = alb
        coc = origin.get("CustomOriginConfig")
        if coc:
            coc["OriginReadTimeout"] = int(os.environ.get("CF_API_ORIGIN_READ_TIMEOUT", "120"))
            coc["OriginKeepaliveTimeout"] = int(os.environ.get("CF_API_ORIGIN_KEEPALIVE_TIMEOUT", "60"))
        break
else:
    raise SystemExit("ApiOrigin not found in CloudFront config")
json.dump(cfg, open(path, "w"))
PY
aws cloudfront update-distribution --id "$CF_DIST_ID" --if-match "$ETAG" \
  --distribution-config "file://${DIST_TMP}" >/dev/null
echo "CloudFront update submitted (propagation ~2-5 min)"
