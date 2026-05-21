#!/usr/bin/env bash
# Fail the build if the login entry bundle depends on heavy route-only vendors.
set -euo pipefail

DIST_DIR="${1:-frontend/dist}"
INDEX_HTML="${DIST_DIR}/index.html"

if [[ ! -f "$INDEX_HTML" ]]; then
  echo "Missing ${INDEX_HTML}. Run: (cd frontend && npm run build)"
  exit 1
fi

BLOCKED_VENDOR_CHUNKS=(
  syntax-highlighter
  framer-motion
  recharts
)

html="$(cat "$INDEX_HTML")"
for chunk in "${BLOCKED_VENDOR_CHUNKS[@]}"; do
  if grep -q "$chunk" <<<"$html"; then
    echo "Login entry preload must not reference ${chunk} (see index.html)."
    exit 1
  fi
done

entry_scripts="$(grep -oE '/assets/index-[^"]+\.js' "$INDEX_HTML" | sort -u || true)"
if [[ -z "$entry_scripts" ]]; then
  echo "No entry script found in ${INDEX_HTML}."
  exit 1
fi

while IFS= read -r script; do
  [[ -z "$script" ]] && continue
  script_path="${DIST_DIR}${script}"
  if [[ ! -f "$script_path" ]]; then
    echo "Missing built entry script: ${script_path}"
    exit 1
  fi
  for chunk in "${BLOCKED_VENDOR_CHUNKS[@]}"; do
    if grep -q "${chunk}" "$script_path"; then
      echo "Entry script ${script} must not import ${chunk}."
      exit 1
    fi
  done
done <<<"$entry_scripts"

echo "Login bundle check passed (${DIST_DIR})."
