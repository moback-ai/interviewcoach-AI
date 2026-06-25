#!/usr/bin/env bash
# One-time setup: commits from Cursor (or any agent) show Govardhan Reddy only.
set -euo pipefail

NAME="${GIT_AUTHOR_NAME:-Govardhan Reddy}"
EMAIL="${GIT_AUTHOR_EMAIL:-90597616+govardhanreddy66@users.noreply.github.com}"
HOOKS_DIR="${HOME}/.githooks-global"

git config --global user.name "$NAME"
git config --global user.email "$EMAIL"
git config --global core.hooksPath "$HOOKS_DIR"

if [[ -d .git ]]; then
  git config --local user.name "$NAME"
  git config --local user.email "$EMAIL"
  git config --local core.hooksPath .githooks
fi

echo "Git author: $(git config user.name) <$(git config user.email)>"
echo "Hooks: $(git config core.hooksPath)"
