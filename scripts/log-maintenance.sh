#!/usr/bin/env bash
set -euo pipefail

LOG_ROOT="${LOG_ROOT:-/apps/logs}"
LIVE_DIR="${LIVE_DIR:-$LOG_ROOT/live}"
ARCHIVE_DIR="${ARCHIVE_DIR:-$LOG_ROOT/archive}"
SIZE_LIMIT_BYTES="${SIZE_LIMIT_BYTES:-2147483648}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
KEEP_RECENT_LOGS="${KEEP_RECENT_LOGS:-10}"
KEEP_ARCHIVES="${KEEP_ARCHIVES:-6}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$LIVE_DIR" "$ARCHIVE_DIR"

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

current_target="$(readlink -f "$LIVE_DIR/deploy-current.log" || true)"
before_bytes="$(total_size)"
archived_count=0
deleted_archives=0

while IFS= read -r -d '' candidate; do
  if [[ -n "$current_target" && "$(readlink -f "$candidate")" == "$current_target" ]]; then
    continue
  fi

  archive_file="$ARCHIVE_DIR/$(basename "$candidate").$TIMESTAMP.zip"
  archive_single_file "$candidate" "$archive_file"
  archived_count=$((archived_count + 1))
done < <(
  find "$LIVE_DIR" -maxdepth 1 -type f -name '*.log' -mtime +"$RETENTION_DAYS" -print0 2>/dev/null
)

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
  else
    mapfile -d '' log_candidates < <(
      find "$LIVE_DIR" -maxdepth 1 -type f -name '*.log' -print0 2>/dev/null |
        while IFS= read -r -d '' path; do
          printf '%s %s\0' "$(file_size_bytes "$path")" "$path"
        done |
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
    if [[ -z "$candidate" ]]; then
      continue
    fi
    if [[ -n "$current_target" && "$(readlink -f "$candidate")" == "$current_target" ]]; then
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
  "before_bytes": $before_bytes,
  "after_bytes": $after_bytes,
  "size_limit_bytes": $SIZE_LIMIT_BYTES,
  "retention_days": $RETENTION_DAYS,
  "keep_recent_logs": $KEEP_RECENT_LOGS,
  "keep_archives": $KEEP_ARCHIVES,
  "archived_logs": $archived_count,
  "deleted_archives": $deleted_archives,
  "generated_at": "$TIMESTAMP"
}
EOFJSON
