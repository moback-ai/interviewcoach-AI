#!/usr/bin/env bash
# Delete old GitHub Actions workflow runs (keeps the Actions tab readable).
# Usage: ./scripts/cleanup-github-actions-runs.sh [--keep N] [--dry-run]
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-moback-ai/interviewcoach-AI}"
KEEP="${KEEP:-5}"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep) KEEP="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

RUN_IDS=()
while IFS= read -r id; do
  RUN_IDS+=("$id")
done < <(
  gh api --paginate "repos/${REPO}/actions/runs?per_page=100" \
    --jq '.workflow_runs | sort_by(.created_at) | reverse | .[].id'
)

total="${#RUN_IDS[@]}"
if (( total <= KEEP )); then
  echo "Only ${total} run(s) found — nothing to delete (keeping ${KEEP})."
  exit 0
fi

to_delete=("${RUN_IDS[@]:KEEP}")
echo "Repository: ${REPO}"
echo "Total runs: ${total} — deleting $(( total - KEEP )) (keeping newest ${KEEP})"

for id in "${to_delete[@]}"; do
  if (( DRY_RUN )); then
    echo "[dry-run] would delete run ${id}"
  else
    gh api --method DELETE "repos/${REPO}/actions/runs/${id}" >/dev/null
    echo "Deleted run ${id}"
  fi
done

echo "Done."
