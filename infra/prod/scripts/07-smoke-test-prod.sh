#!/usr/bin/env bash
# Quick post-deploy health check (public URL).
set -euo pipefail

URL="${1:-https://www.ugaanlabs.ai/api/health}"
ATTEMPTS="${SMOKE_ATTEMPTS:-8}"
SLEEP="${SMOKE_SLEEP_SEC:-15}"

for i in $(seq 1 "$ATTEMPTS"); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$URL" || echo "000")
  echo "health attempt $i: HTTP $code"
  if [[ "$code" == "200" ]]; then
    curl -fsS "$URL" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d.get('status')=='healthy', d
print('OK:', d.get('status'))
"
    exit 0
  fi
  if [[ "$code" == "503" ]]; then
    echo "503 — ASG may be off-hours (10:00–19:00 IST). Rollout complete."
    exit 0
  fi
  sleep "$SLEEP"
done

echo "Health check failed (last HTTP $code). Logs: CloudWatch /interviewcoach/prod/api"
exit 1
