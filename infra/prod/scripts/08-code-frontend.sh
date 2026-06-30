#!/usr/bin/env bash
# Build frontend and sync to S3 — devsecops-platform GitHub Actions only.
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"

if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm is required (install Node on the CI runner)."
  exit 1
fi

# shellcheck disable=SC1091
source "$(dirname "$0")/load-prod-env.sh"
