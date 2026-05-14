#!/usr/bin/env bash
set -euo pipefail

LOG_ROOT="${LOG_ROOT:-/apps/logs}"
LIVE_DIR="${LIVE_DIR:-$LOG_ROOT/live}"
ARCHIVE_DIR="${ARCHIVE_DIR:-$LOG_ROOT/archive}"
TMP_DIR="${TMP_DIR:-$LOG_ROOT/tmp}"
PM2_LOG_DIR="${PM2_LOG_DIR:-/home/ubuntu/.pm2/logs}"
SIZE_LIMIT_BYTES="${SIZE_LIMIT_BYTES:-2147483648}"
KEEP_DEPLOY_LOGS="${KEEP_DEPLOY_LOGS:-8}"
KEEP_PM2_LINES="${KEEP_PM2_LINES:-5000}"
FORCE_ARCHIVE="${FORCE_ARCHIVE:-0}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$LIVE_DIR" "$ARCHIVE_DIR" "$TMP_DIR"

active_size_bytes() {
  local total=0
  local file
  while IFS= read -r -d '' file; do
    total=$((total + $(stat -c %s "$file")))
  done < <(
    find "$LIVE_DIR" "$PM2_LOG_DIR" \
      -type f \
      \( -name '*.log' -o -name '*.txt' \) \
      -print0 2>/dev/null
  )
  echo "$total"
}

STAGING_DIR="$(mktemp -d "$TMP_DIR/archive-$TIMESTAMP-XXXXXX")"
ARCHIVE_REQUIRED=0

CURRENT_DEPLOY_TARGET="$(readlink -f "$LIVE_DIR/deploy-current.log" || true)"
mapfile -t DEPLOY_LOGS < <(find "$LIVE_DIR" -maxdepth 1 -type f -name 'deploy-*.log' | sort)

if ((${#DEPLOY_LOGS[@]} > KEEP_DEPLOY_LOGS)); then
  DEPLOY_TO_ARCHIVE_COUNT=$((${#DEPLOY_LOGS[@]} - KEEP_DEPLOY_LOGS))
  for deploy_log in "${DEPLOY_LOGS[@]:0:$DEPLOY_TO_ARCHIVE_COUNT}"; do
    if [[ -n "$CURRENT_DEPLOY_TARGET" && "$(readlink -f "$deploy_log")" == "$CURRENT_DEPLOY_TARGET" ]]; then
      continue
    fi
    mkdir -p "$STAGING_DIR/live"
    mv "$deploy_log" "$STAGING_DIR/live/"
    ARCHIVE_REQUIRED=1
  done
fi

TOTAL_ACTIVE_SIZE="$(active_size_bytes)"
if [[ "$FORCE_ARCHIVE" == "1" || "$TOTAL_ACTIVE_SIZE" -gt "$SIZE_LIMIT_BYTES" ]]; then
  for pm2_file in "$PM2_LOG_DIR/backend-error.log" "$PM2_LOG_DIR/backend-out.log"; do
    if [[ ! -f "$pm2_file" ]]; then
      continue
    fi

    mkdir -p "$STAGING_DIR/pm2"
    cp "$pm2_file" "$STAGING_DIR/pm2/$(basename "$pm2_file").$TIMESTAMP"
    tail -n "$KEEP_PM2_LINES" "$pm2_file" >"$pm2_file.tmp"
    mv "$pm2_file.tmp" "$pm2_file"
    ARCHIVE_REQUIRED=1
  done
fi

if [[ "$ARCHIVE_REQUIRED" == "1" ]]; then
  ARCHIVE_FILE="$ARCHIVE_DIR/log-archive-$TIMESTAMP.zip"
  python3 - "$STAGING_DIR" "$ARCHIVE_FILE" <<'PY'
import os
import sys
import zipfile

staging_dir, archive_file = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(archive_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for root, _, files in os.walk(staging_dir):
        for name in files:
            absolute_path = os.path.join(root, name)
            relative_path = os.path.relpath(absolute_path, staging_dir)
            zf.write(absolute_path, arcname=relative_path)
PY

  cat >"$ARCHIVE_DIR/log-archive-$TIMESTAMP.json" <<EOFJSON
{
  "created_at": "$TIMESTAMP",
  "log_root": "$LOG_ROOT",
  "size_limit_bytes": $SIZE_LIMIT_BYTES,
  "active_size_before_cleanup": $TOTAL_ACTIVE_SIZE
}
EOFJSON

  rm -rf "$STAGING_DIR"
  echo "Archived logs into $ARCHIVE_FILE"
else
  rm -rf "$STAGING_DIR"
  echo "No log archive cleanup was required."
fi

echo "Active log size after cleanup: $(active_size_bytes) bytes"
