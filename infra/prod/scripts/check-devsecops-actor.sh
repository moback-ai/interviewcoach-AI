#!/usr/bin/env bash
# Allow only DevSecOps GitHub users to run production workflows/scripts.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh" 2>/dev/null || true

_finish() {
  local code="$1"
  if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    return "$code"
  fi
  exit "$code"
}

ALLOWED="${DEVSECOPS_GITHUB_ACTORS:-govardhanreddy66,KFKishore23}"
ACTOR="${GITHUB_ACTOR:-${DEVSECOPS_ACTOR:-}}"

if [[ -z "$ACTOR" ]]; then
  echo "ERROR: GITHUB_ACTOR not set (run from GitHub Actions or set DEVSECOPS_ACTOR)." >&2
  _finish 1
fi

IFS=',' read -ra USERS <<< "$ALLOWED"
for u in "${USERS[@]}"; do
  u="${u// /}"
  if [[ "$ACTOR" == "$u" ]]; then
    echo "DevSecOps actor OK: $ACTOR"
    _finish 0
  fi
done

echo "ERROR: Denied. Only DevSecOps may run production operations (actor: $ACTOR)." >&2
echo "Allowed: $ALLOWED" >&2
_finish 1
