#!/usr/bin/env bash
# Archive and prune logs under LOG_ROOT.
#
# Defaults:
#   - Keep only 1 day of live/server logs (Sunday run enforces weekly cleanup)
#   - Zip any single log file larger than 10 MB, then remove the source file
#   - If total log usage exceeds SIZE_LIMIT_BYTES, archive oldest files first
#
# Env:
#   LOG_ROOT, RETENTION_DAYS (default 1), FILE_ZIP_THRESHOLD_BYTES (default 10MB),
#   SIZE_LIMIT_BYTES (default 2GB), KEEP_RECENT_LOGS, KEEP_ARCHIVES, FORCE_SUNDAY_CLEANUP
set -euo pipefail

LOG_ROOT="${LOG_ROOT:-/apps/logs}"
LIVE_DIR="${LIVE_DIR:-$LOG_ROOT/live}"
ARCHIVE_DIR="${ARCHIVE_DIR:-$LOG_ROOT/archive}"
SERVER_DIR="${SERVER_DIR:-$LOG_ROOT/server}"
FILE_ZIP_THRESHOLD_BYTES="${FILE_ZIP_THRESHOLD_BYTES:-10485760}"
SIZE_LIMIT_BYTES="${SIZE_LIMIT_BYTES:-2147483648}"
RETENTION_DAYS="${RETENTION_DAYS:-1}"
KEEP_RECENT_LOGS="${KEEP_RECENT_LOGS:-5}"
KEEP_ARCHIVES="${KEEP_ARCHIVES:-3}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DAY_OF_WEEK="$(date -u +%w)"
FORCE_SUNDAY_CLEANUP="${FORCE_SUNDAY_CLEANUP:-0}"

mkdir -p "$LIVE_DIR" "$ARCHIVE_DIR" "$SERVER_DIR"

file_size_bytes() {
  local target="$1"
  if stat -c '%s' /dev/null >/dev/null 2>&1; then
    stat -c '%s' "$target"
  else
    stat -f '%z' "$target"
  fi
}

total_size() {
  local sum=0
  local size
  while IFS= read -r -d '' file; do
    size="$(file_size_bytes "$file")"
    sum=$((sum + size))
  done < <(find "$LOG_ROOT" -type f -print0 2>/dev/null)
  echo "$sum"
}

archive_single_file() {
  local source_file="$1"
  local archive_name="$2"

  python3 - "$source_file" "$archive_name" <<'PY'
import os
import sys
import zipfile

source_file, archive_name = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(archive_name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    archive.write(source_file, arcname=os.path.basename(source_file))
PY

  rm -f "$source_file"
}

current_target="$(readlink -f "$LIVE_DIR/deploy-current.log" 2>/dev/null || true)"
before_bytes="$(total_size)"
archived_count=0
deleted_archives=0
oversize_archived=0

should_skip_file() {
  local candidate="$1"
  if [[ -z "$candidate" ]]; then
    return 0
  fi
  if [[ -n "$current_target" && "$(readlink -f "$candidate")" == "$current_target" ]]; then
    return 0
  fi
  return 1
}

# Zip individual files that exceed 10 MB
while IFS= read -r -d '' candidate; do
  if ! should_skip_file "$candidate"; then
    continue
  fi
  size="$(file_size_bytes "$candidate")"
  if (( size < FILE_ZIP_THRESHOLD_BYTES )); then
    continue
  fi
  archive_file="$ARCHIVE_DIR/$(basename "$candidate").oversize.$TIMESTAMP.zip"
  archive_single_file "$candidate" "$archive_file"
  archived_count=$((archived_count + 1))
  oversize_archived=$((oversize_archived + 1))
done < <(
  find "$LOG_ROOT" -type f \( -name '*.log' -o -name '*.txt' -o -name '*.json' \) -print0 2>/dev/null
)

# Remove logs older than retention window (default: 1 day)
while IFS= read -r -d '' candidate; do
  if ! should_skip_file "$candidate"; then
    continue
  fi
  archive_file="$ARCHIVE_DIR/$(basename "$candidate").$TIMESTAMP.zip"
  archive_single_file "$candidate" "$archive_file"
  archived_count=$((archived_count + 1))
done < <(
  find "$LIVE_DIR" -maxdepth 1 -type f -name '*.log' -mtime +"$RETENTION_DAYS" -print0 2>/dev/null
)

while IFS= read -r -d '' candidate; do
  base_name="$(basename "$candidate")"
  if [[ "$base_name" == "api-failures.log" ]]; then
    continue
  fi
  if ! should_skip_file "$candidate"; then
    continue
  fi
  archive_file="$ARCHIVE_DIR/server-$(echo "$candidate" | tr '/' '-').$TIMESTAMP.zip"
  archive_single_file "$candidate" "$archive_file"
  archived_count=$((archived_count + 1))
done < <(
  find "$SERVER_DIR" -type f \( -name '*.log' -o -name '*.txt' \) -mtime +"$RETENTION_DAYS" -print0 2>/dev/null
)

# Sunday cleanup: drop archived zip bundles older than retention window
if [[ "$DAY_OF_WEEK" == "0" || "$FORCE_SUNDAY_CLEANUP" == "1" ]]; then
  while IFS= read -r -d '' candidate; do
    rm -f "$candidate"
    deleted_archives=$((deleted_archives + 1))
  done < <(
    find "$ARCHIVE_DIR" -maxdepth 1 -type f -name '*.zip' -mtime +"$RETENTION_DAYS" -print0 2>/dev/null
  )
fi

current_size="$(total_size)"
if (( current_size > SIZE_LIMIT_BYTES )); then
  mapfile -d '' log_candidates < <(find "$LIVE_DIR" -maxdepth 1 -type f -name '*.log' -print0 2>/dev/null)

  if stat -c '%Y %n' /dev/null >/dev/null 2>&1; then
    mapfile -d '' log_candidates < <(
      find "$LIVE_DIR" -maxdepth 1 -type f -name '*.log' -printf '%T@ %p\0' 2>/dev/null |
        sort -z -n |
        while IFS= read -r -d '' entry; do
          printf '%s\0' "${entry#* }"
        done
    )
  fi

  keep_from_index=0
  if (( ${#log_candidates[@]} > KEEP_RECENT_LOGS )); then
    keep_from_index=$((${#log_candidates[@]} - KEEP_RECENT_LOGS))
  fi

  for (( index = 0; index < keep_from_index; index++ )); do
    candidate="${log_candidates[$index]}"
    if ! should_skip_file "$candidate"; then
      continue
    fi
    archive_file="$ARCHIVE_DIR/$(basename "$candidate").$TIMESTAMP.zip"
    archive_single_file "$candidate" "$archive_file"
    archived_count=$((archived_count + 1))
    current_size="$(total_size)"
    if (( current_size <= SIZE_LIMIT_BYTES )); then
      break
    fi
  done
fi

current_size="$(total_size)"
if (( current_size > SIZE_LIMIT_BYTES )); then
  mapfile -t archive_candidates < <(find "$ARCHIVE_DIR" -maxdepth 1 -type f -name '*.zip' | sort)
  while (( ${#archive_candidates[@]} > KEEP_ARCHIVES && current_size > SIZE_LIMIT_BYTES )); do
    oldest_archive="${archive_candidates[0]}"
    rm -f "$oldest_archive"
    archive_candidates=("${archive_candidates[@]:1}")
    deleted_archives=$((deleted_archives + 1))
    current_size="$(total_size)"
  done
fi

after_bytes="$(total_size)"

cat <<EOFJSON
{
  "log_root": "$LOG_ROOT",
  "server_dir": "$SERVER_DIR",
  "before_bytes": $before_bytes,
  "after_bytes": $after_bytes,
  "size_limit_bytes": $SIZE_LIMIT_BYTES,
  "file_zip_threshold_bytes": $FILE_ZIP_THRESHOLD_BYTES,
  "retention_days": $RETENTION_DAYS,
  "keep_recent_logs": $KEEP_RECENT_LOGS,
  "keep_archives": $KEEP_ARCHIVES,
  "sunday_cleanup": $([[ "$DAY_OF_WEEK" == "0" || "$FORCE_SUNDAY_CLEANUP" == "1" ]] && echo true || echo false),
  "archived_logs": $archived_count,
  "oversize_archived": $oversize_archived,
  "deleted_archives": $deleted_archives,
  "generated_at": "$TIMESTAMP"
}
EOFJSON
