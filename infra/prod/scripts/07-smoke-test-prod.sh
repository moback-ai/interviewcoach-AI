#!/usr/bin/env bash
# Post-deploy verification: readiness, service-hours, and frontend entry bundle.
set -euo pipefail

BASE_URL="${1:-https://www.ugaanlabs.ai}"
READY_URL="${BASE_URL%/}/api/health/ready"
SERVICE_HOURS_URL="${BASE_URL%/}/api/service-hours"
INDEX_URL="${BASE_URL%/}/"
ATTEMPTS="${SMOKE_ATTEMPTS:-10}"
SLEEP="${SMOKE_SLEEP_SEC:-15}"

if [[ "${ALLOW_OFF_HOURS_DEPLOY:-}" != "1" ]]; then
  hour="$(TZ=Asia/Kolkata date +%H)"
  if (( 10#${hour} < 10 || 10#${hour} >= 19 )); then
    echo "::error::Smoke test blocked outside 10:00–19:00 IST (ASG may be scaled to 0)."
    echo "Set ALLOW_OFF_HOURS_DEPLOY=1 only for emergency verification."
    exit 1
  fi
fi

check_ready() {
  local code
  code=$(curl -s -o /tmp/ic-ready.json -w '%{http_code}' "$READY_URL" || echo "000")
  echo "readiness: HTTP $code"
  if [[ "$code" != "200" ]]; then
    return 1
  fi
  python3 - <<'PY'
import json
with open("/tmp/ic-ready.json", encoding="utf-8") as fh:
    data = json.load(fh)
assert data.get("ready") is True, data
assert data.get("status") == "ready", data
print("readiness OK")
PY
}

for i in $(seq 1 "$ATTEMPTS"); do
  echo "smoke attempt $i/$ATTEMPTS"
  if check_ready; then
    break
  fi
  if [[ "$i" -eq "$ATTEMPTS" ]]; then
    echo "Readiness check failed after ${ATTEMPTS} attempts."
    exit 1
  fi
  sleep "$SLEEP"
done

code=$(curl -s -o /dev/null -w '%{http_code}' "$SERVICE_HOURS_URL" || echo "000")
echo "service-hours: HTTP $code"
[[ "$code" == "200" ]] || { echo "service-hours check failed"; exit 1; }

code=$(curl -s -o /tmp/ic-index.html -w '%{http_code}' "$INDEX_URL" || echo "000")
echo "frontend index: HTTP $code"
[[ "$code" == "200" ]] || { echo "frontend index check failed"; exit 1; }
grep -q '/assets/index-' /tmp/ic-index.html || { echo "frontend entry bundle missing from index.html"; exit 1; }

echo "Smoke checks passed for ${BASE_URL}"
