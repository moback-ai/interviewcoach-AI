#!/usr/bin/env bash
# Rewrite branch history: normalize authors and strip unwanted commit trailers.
set -euo pipefail

AUTHOR_NAME="${AUTHOR_NAME:-Govardhan Reddy}"
AUTHOR_EMAIL="${AUTHOR_EMAIL:-90597616+govardhanreddy66@users.noreply.github.com}"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Run from inside a git repository." >&2
  exit 1
fi

branch="$(git branch --show-current)"
if [[ -z "$branch" ]]; then
  echo "Detached HEAD — checkout a branch first." >&2
  exit 1
fi

if ! git diff-index --quiet HEAD -- 2>/dev/null || [[ -n "$(git status --porcelain)" ]]; then
  echo "Commit or stash local changes before rewriting history." >&2
  exit 1
fi

echo "Rewriting branch: $branch"
echo "Author target: $AUTHOR_NAME <$AUTHOR_EMAIL>"

export AUTHOR_NAME AUTHOR_EMAIL
export FILTER_BRANCH_SQUELCH_WARNING=1

git filter-branch -f \
  --env-filter '
    unwanted=0
    case "$GIT_AUTHOR_EMAIL" in
      codex@openai.com|cursoragent@cursor.com|*copilot*) unwanted=1 ;;
    esac
    case "$GIT_AUTHOR_NAME" in
      Codex|Cursor|*Copilot*|*copilot*) unwanted=1 ;;
    esac
    if [ "$unwanted" = 1 ]; then
      export GIT_AUTHOR_NAME="$AUTHOR_NAME"
      export GIT_AUTHOR_EMAIL="$AUTHOR_EMAIL"
    fi

    unwanted=0
    case "$GIT_COMMITTER_EMAIL" in
      codex@openai.com|cursoragent@cursor.com|*copilot*) unwanted=1 ;;
    esac
    case "$GIT_COMMITTER_NAME" in
      Codex|Cursor|*Copilot*|*copilot*) unwanted=1 ;;
    esac
    if [ "$unwanted" = 1 ]; then
      export GIT_COMMITTER_NAME="$AUTHOR_NAME"
      export GIT_COMMITTER_EMAIL="$AUTHOR_EMAIL"
    fi
  ' \
  --msg-filter '
    sed \
      -e "/^Co-authored-by: Cursor <cursoragent@cursor.com>$/d" \
      -e "/^Made-with: Cursor$/d" \
      -e "/^Co-authored-by:.*[Cc]opilot/d" \
      -e "/^Co-authored-by: Codex/d" \
      -e "/^Co-authored-by:.*codex@openai\.com/d" \
      -e "s|moback-ai/codex/|moback-ai/|g" \
      -e "s|codex/||g" \
      -e "s|Codex/||g"
  ' \
  "$branch"

echo "Done. Publish: git push --force-with-lease origin $branch"
