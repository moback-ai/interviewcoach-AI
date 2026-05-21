#!/usr/bin/env bash
# One-time helper: create develop from main and print GitHub settings to apply.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== InterviewCoach branch governance setup ==="

if ! git rev-parse --verify develop >/dev/null 2>&1; then
  git fetch origin main
  git checkout -b develop origin/main
  echo "Created local branch develop from origin/main"
else
  git checkout develop
  git merge origin/main --no-edit || true
  echo "Updated local develop from origin/main"
fi

echo ""
echo "Push develop to GitHub:"
echo "  git push -u origin develop"
echo ""
echo "In GitHub → Settings → Branches:"
echo "  1. Set default branch to develop"
echo "  2. Protect develop and main (PR required, 1 approval, code owners, lint check)"
echo "  3. Disable auto-merge on pull requests"
echo ""
echo "Workflows enabled:"
echo "  - auto-deploy-develop.yml (deploy develop + develop/*)"
echo "  - monthly-sync-main-from-develop.yml (develop → main monthly)"
echo "  - auto-deploy-main.yml (disabled)"
