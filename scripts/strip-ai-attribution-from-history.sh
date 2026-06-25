#!/usr/bin/env bash
# Rewrite git history: AI tool authors → Govardhan Reddy; strip AI co-author trailers.
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
    ai_author=0
    case "$GIT_AUTHOR_EMAIL" in
      codex@openai.com|cursoragent@cursor.com|*copilot*) ai_author=1 ;;
    esac
    case "$GIT_AUTHOR_NAME" in
      Codex|Cursor|*Copilot*|*copilot*) ai_author=1 ;;
    esac
    if [ "$ai_author" = 1 ]; then
      export GIT_AUTHOR_NAME="$AUTHOR_NAME"
      export GIT_AUTHOR_EMAIL="$AUTHOR_EMAIL"
    fi

    ai_committer=0
    case "$GIT_COMMITTER_EMAIL" in
      codex@openai.com|cursoragent@cursor.com|*copilot*) ai_committer=1 ;;
    esac
    case "$GIT_COMMITTER_NAME" in
      Codex|Cursor|*Copilot*|*copilot*) ai_committer=1 ;;
    esac
    if [ "$ai_committer" = 1 ]; then
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
      -e "s|Codex/||g"
  ' \
  "$branch"

echo "Done. Verify:"
echo "  git log --author=Codex --oneline | wc -l   # expect 0"
echo "  git log --grep=codex -i --oneline | wc -l  # expect 0"
echo "Publish: git push --force-with-lease origin $branch"
