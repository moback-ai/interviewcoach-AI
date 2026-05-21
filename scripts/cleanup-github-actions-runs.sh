#!/usr/bin/env bash
# Prune GitHub Actions runs: keep last 2 days, cap total at 10, drop old failures.
# Usage: ./scripts/cleanup-github-actions-runs.sh [--max N] [--days N] [--dry-run]
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-moback-ai/interviewcoach-AI}"
MAX_RUNS="${MAX_RUNS:-10}"
KEEP_DAYS="${KEEP_DAYS:-2}"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max) MAX_RUNS="$2"; shift 2 ;;
    --days) KEEP_DAYS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

CUTOFF_EPOCH=$(($(date +%s) - KEEP_DAYS * 86400))

to_epoch() {
  local ts="$1"
  date -j -f "%Y-%m-%dT%H:%M:%SZ" "$ts" "+%s" 2>/dev/null \
    || date -d "$ts" "+%s" 2>/dev/null \
    || echo 0
}

is_failed_conclusion() {
  case "${1:-}" in
    failure|cancelled|timed_out|startup_failure|action_required|stale) return 0 ;;
    *) return 1 ;;
  esac
}

RUNS_TSV=()
while IFS=$'\t' read -r id created conclusion status; do
  RUNS_TSV+=("${id}	${created}	${conclusion}	${status}")
done < <(
  gh api --paginate "repos/${REPO}/actions/runs?per_page=100" \
    --jq '.workflow_runs[] | [.id, .created_at, (.conclusion // ""), .status] | @tsv'
)

total="${#RUNS_TSV[@]}"
if (( total == 0 )); then
  echo "No workflow runs found."
  exit 0
fi

declare -a DELETE_IDS=()

for row in "${RUNS_TSV[@]}"; do
  IFS=$'\t' read -r id created conclusion status <<< "$row"

  created_epoch=$(to_epoch "$created")

  within_window=0
  if (( created_epoch >= CUTOFF_EPOCH )); then
    within_window=1
  fi

  is_failed=0
  if [[ "$status" == "completed" ]] && is_failed_conclusion "$conclusion"; then
    is_failed=1
  fi

  # Drop completed failures (keep in-flight runs).
  if (( is_failed )); then
    DELETE_IDS+=("$id")
    continue
  fi

  # Drop anything older than the keep window.
  if (( ! within_window )); then
    DELETE_IDS+=("$id")
  fi
done

# If still above max, delete oldest runs outside the keep window first, then oldest overall.
remaining=$(( total - ${#DELETE_IDS[@]} ))
if (( remaining > MAX_RUNS )); then
  declare -A DELETE_MAP=()
  for did in "${DELETE_IDS[@]}"; do DELETE_MAP[$did]=1; done

  SORTED_OLDEST=()
  while IFS= read -r line; do
    SORTED_OLDEST+=("$line")
  done < <(
    for row in "${RUNS_TSV[@]}"; do
      IFS=$'\t' read -r id created conclusion status <<< "$row"
      [[ -n "${DELETE_MAP[$id]:-}" ]] && continue
      echo "${created} ${id}"
    done | sort
  )

  excess=$(( remaining - MAX_RUNS ))
  for (( i = 0; i < excess && i < ${#SORTED_OLDEST[@]}; i++ )); do
    id=$(echo "${SORTED_OLDEST[$i]}" | awk '{print $NF}')
    DELETE_IDS+=("$id")
  done
fi

# Unique IDs
UNIQUE_DELETE=()
while IFS= read -r line; do
  UNIQUE_DELETE+=("$line")
done < <(printf '%s\n' "${DELETE_IDS[@]}" | awk '!seen[$0]++')

if ((${#UNIQUE_DELETE[@]} == 0)); then
  echo "Repository: ${REPO} — ${total} run(s), nothing to delete (keep ${KEEP_DAYS}d, max ${MAX_RUNS})."
  exit 0
fi

echo "Repository: ${REPO}"
echo "Total runs: ${total} — deleting ${#UNIQUE_DELETE[@]} (keep ${KEEP_DAYS} days, max ${MAX_RUNS} runs)"

for id in "${UNIQUE_DELETE[@]}"; do
  if (( DRY_RUN )); then
    echo "[dry-run] would delete run ${id}"
  else
    gh api --method DELETE "repos/${REPO}/actions/runs/${id}" >/dev/null
    echo "Deleted run ${id}"
  fi
done

echo "Done."
