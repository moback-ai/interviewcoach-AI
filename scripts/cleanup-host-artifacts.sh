#!/usr/bin/env bash
# Prune old deploy releases, build/dist artifacts, and logs on EC2 (or local project tree).
#
# Policy:
#   - Keep the active current + stable release symlinks (always)
#   - Keep the newest N successful release directories (default: 2)
#   - Move older releases to archive/<name>_DD_MM_YYYY, then delete archives older than N days
#   - Run log-maintenance.sh on LOG_ROOT
#   - Remove stale /tmp build folders (frontend-dist, deploy-*, etc.)
#
# Env:
#   KEEP_SUCCESSFUL_RELEASES (default 2)
#   ARCHIVE_BEFORE_DELETE (default 1)
#   DELETE_ARCHIVED_AFTER_DAYS (default 7)
#   LOG_ROOT, LOG_RETENTION_DAYS
#   BACKEND_RELEASES_DIR, FRONTEND_RELEASES_DIR
#   PROJECT_ROOT (optional — also clean repo dist/build/.vite)
#   DRY_RUN (1 = print only)
set -euo pipefail

KEEP_SUCCESSFUL_RELEASES="${KEEP_SUCCESSFUL_RELEASES:-2}"
ARCHIVE_BEFORE_DELETE="${ARCHIVE_BEFORE_DELETE:-1}"
DELETE_ARCHIVED_AFTER_DAYS="${DELETE_ARCHIVED_AFTER_DAYS:-7}"
LOG_ROOT="${LOG_ROOT:-/apps/logs}"
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-3}"
BACKEND_RELEASES_DIR="${BACKEND_RELEASES_DIR:-/apps/backend/releases}"
FRONTEND_RELEASES_DIR="${FRONTEND_RELEASES_DIR:-/var/www/interview/releases}"
BACKEND_ROOT="${BACKEND_ROOT:-/apps/backend}"
FRONTEND_ROOT="${FRONTEND_ROOT:-/var/www/interview}"
PROJECT_ROOT="${PROJECT_ROOT:-}"
DRY_RUN="${DRY_RUN:-0}"
DEPLOY_RUNS_DIR="${DEPLOY_RUNS_DIR:-/apps/deployments/runs}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "[cleanup] $*"; }

run_cmd() {
  if [[ "$DRY_RUN" == "1" ]]; then
    log "DRY-RUN: $*"
  else
    eval "$@"
  fi
}

date_suffix() {
  date -u +%d_%m_%Y
}

resolve_link() {
  local link_path="$1"
  if [[ -L "$link_path" || -d "$link_path" ]]; then
    readlink -f "$link_path" 2>/dev/null || true
  fi
}

# Keep protected paths + newest KEEP_SUCCESSFUL_RELEASES unique directories.
prune_release_directory() {
  local releases_dir="$1"
  local current_link="$2"
  local stable_link="$3"
  local archive_dir="$4"
  local use_sudo="${5:-0}"

  [[ -d "$releases_dir" ]] || return 0

  local -a protected=()
  local current_path stable_path
  current_path="$(resolve_link "$current_link")"
  stable_path="$(resolve_link "$stable_link")"
  [[ -n "$current_path" ]] && protected+=("$current_path")
  [[ -n "$stable_path" && "$stable_path" != "$current_path" ]] && protected+=("$stable_path")

  local sudo_prefix=()
  if [[ "$use_sudo" == "1" ]]; then
    sudo_prefix=(sudo)
  fi
  "${sudo_prefix[@]}" mkdir -p "$archive_dir"

  mapfile -t sorted_dirs < <(
    find "$releases_dir" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null |
      sort -rn |
      awk '{ $1=""; sub(/^ /,""); print }'
  )

  declare -A keep_lookup=()
  local entry resolved is_protected=0
  for entry in "${protected[@]}"; do
    [[ -n "$entry" ]] && keep_lookup["$entry"]=1
  done

  for dir_path in "${sorted_dirs[@]}"; do
    resolved="$(readlink -f "$dir_path")"
    [[ -n "${keep_lookup[$resolved]:-}" ]] && continue

    if [[ "${#keep_lookup[@]}" -lt "$KEEP_SUCCESSFUL_RELEASES" ]]; then
      keep_lookup["$resolved"]=1
      continue
    fi
    local base_name archived_path
    base_name="$(basename "$resolved")"
    archived_path="$archive_dir/${base_name}_$(date_suffix)"
    if [[ "$ARCHIVE_BEFORE_DELETE" == "1" ]]; then
      log "Archive $resolved -> $archived_path"
      run_cmd "${sudo_prefix[@]} mv \"$resolved\" \"$archived_path\""
    else
      log "Remove $resolved"
      run_cmd "${sudo_prefix[@]} rm -rf \"$resolved\""
    fi
  done

  while IFS= read -r -d '' old_archive; do
    log "Delete old archive $old_archive"
    run_cmd "${sudo_prefix[@]} rm -rf \"$old_archive\""
  done < <(
    find "$archive_dir" -mindepth 1 -maxdepth 1 \( -type d -o -type f \) -mtime +"$DELETE_ARCHIVED_AFTER_DAYS" -print0 2>/dev/null
  )
}

prune_temp_build_dirs() {
  local pattern
  for pattern in /tmp/frontend-dist /tmp/deploy-host-toolchain.sh /tmp/nginx-logs.snippet /tmp/interview-nginx.conf; do
    if [[ -e "$pattern" ]]; then
      log "Remove temp $pattern"
      run_cmd "rm -rf \"$pattern\""
    fi
  done
  find /tmp -maxdepth 1 -type d \( -name 'frontend-dist-*' -o -name 'deploy-*' \) -mtime +1 2>/dev/null | while read -r dir; do
    log "Remove stale temp $dir"
    run_cmd "rm -rf \"$dir\""
  done
}

prune_deploy_runs() {
  [[ -d "$DEPLOY_RUNS_DIR" ]] || return 0
  mapfile -t run_dirs < <(find "$DEPLOY_RUNS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort -r)
  local index=0
  for dir_path in "${run_dirs[@]}"; do
    index=$((index + 1))
    if (( index > KEEP_SUCCESSFUL_RELEASES )); then
      local archived="$DEPLOY_RUNS_DIR/archive/$(basename "$dir_path")_$(date_suffix)"
      mkdir -p "$DEPLOY_RUNS_DIR/archive"
      log "Archive deploy run $dir_path"
      run_cmd "mv \"$dir_path\" \"$archived\" 2>/dev/null || rm -rf \"$dir_path\""
    fi
  done
}

prune_project_build_artifacts() {
  local root="$1"
  [[ -d "$root" ]] || return 0
  local rel path archived
  for rel in frontend/dist frontend/build frontend/.vite backend/dist backend/build dist build; do
    path="$root/$rel"
    if [[ -d "$path" ]]; then
      archived="${path}_$(date_suffix)"
      log "Archive project build $path -> $archived"
      run_cmd "mv \"$path\" \"$archived\""
      find "$(dirname "$path")" -maxdepth 1 -type d -name "$(basename "$path")_*" -mtime +"$DELETE_ARCHIVED_AFTER_DAYS" 2>/dev/null | while read -r old; do
        run_cmd "rm -rf \"$old\""
      done
    fi
  done
}

prune_backend_venv_duplicates() {
  # On AI-only hosts, drop duplicate backend venv if no PM2 backend is expected.
  if [[ "${DROP_BACKEND_VENV_ON_AI:-0}" == "1" && -d "$BACKEND_ROOT/venv" ]]; then
    if ! pm2 pid backend >/dev/null 2>&1; then
      log "Remove unused backend venv on AI host"
      run_cmd "rm -rf \"$BACKEND_ROOT/venv\""
    fi
  fi
}

main() {
  log "Starting artifact cleanup (keep $KEEP_SUCCESSFUL_RELEASES releases)"

  prune_release_directory \
    "$BACKEND_RELEASES_DIR" \
    "$BACKEND_ROOT/current" \
    "$BACKEND_ROOT/stable" \
    "$BACKEND_RELEASES_DIR/archive"

  prune_release_directory \
    "$FRONTEND_RELEASES_DIR" \
    "$FRONTEND_ROOT/current" \
    "$FRONTEND_ROOT/stable" \
    "$FRONTEND_RELEASES_DIR/archive" \
    "1"

  prune_temp_build_dirs
  prune_deploy_runs
  prune_backend_venv_duplicates

  if [[ -n "$PROJECT_ROOT" ]]; then
    prune_project_build_artifacts "$PROJECT_ROOT"
  fi

  if [[ -x "$SCRIPT_DIR/log-maintenance.sh" ]]; then
    log "Running log maintenance on $LOG_ROOT"
    if [[ "$DRY_RUN" == "1" ]]; then
      log "DRY-RUN: RETENTION_DAYS=$LOG_RETENTION_DAYS LOG_ROOT=$LOG_ROOT bash log-maintenance.sh"
    else
      RETENTION_DAYS="$LOG_RETENTION_DAYS" LOG_ROOT="$LOG_ROOT" bash "$SCRIPT_DIR/log-maintenance.sh"
    fi
  fi

  log "Cleanup complete"
}

main "$@"
