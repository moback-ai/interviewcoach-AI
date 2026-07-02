#!/usr/bin/env bash
# Block production deploy outside 10:00–19:00 IST unless ALLOW_OFF_HOURS_DEPLOY=1.
set -euo pipefail

if [[ "${ALLOW_OFF_HOURS_DEPLOY:-}" == "1" ]]; then
  echo "Off-hours deploy explicitly allowed (ALLOW_OFF_HOURS_DEPLOY=1)."
  exit 0
fi

hour="$(TZ=Asia/Kolkata date +%H)"
if (( 10#${hour} < 10 || 10#${hour} >= 19 )); then
  echo "::error::Production deploy blocked outside 10:00–19:00 IST."
  echo "Current IST hour: ${hour}"
  echo "Set ALLOW_OFF_HOURS_DEPLOY=1 only for emergency rollback or maintenance."
  exit 1
fi

echo "Within production deploy window (10:00–19:00 IST)."
