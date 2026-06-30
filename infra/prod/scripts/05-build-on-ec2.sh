#!/usr/bin/env bash
# BLOCKED — Prod builds run on GitHub Actions only (.github/workflows/deploy-prod.yml).
set -euo pipefail
echo "ERROR: EC2/local prod builds are disabled."
echo "Use GitHub Actions: Deploy PROD workflow."
exit 1
