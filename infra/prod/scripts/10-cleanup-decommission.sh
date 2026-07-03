#!/usr/bin/env bash
# Step 8 — Decommission Plan B (AI EC2, transcribe sidecar, old secrets keys).
# Run ONLY after 7+ days stable. See devsecops-platform apps/interviewcoach/docs/AWS_DECOMMISSION.md
set -euo pipefail

# shellcheck disable=SC1091
source "$(dirname "$0")/require-devsecops.sh"

SCRIPT_DIR="$(dirname "$0")"

echo "=== Step 8: Decommission Plan B ==="
bash "${SCRIPT_DIR}/../../../scripts/aws-decommission-checklist.sh"
echo ""

# Automated safe cleanup (EC2 terminate is manual if instances still exist)
bash "${SCRIPT_DIR}/10a-cleanup-secrets-legacy.sh"
bash "${SCRIPT_DIR}/10b-cleanup-security-groups.sh"

echo ""
echo "MANUAL if instances still exist:"
echo "  [ ] Terminate AI EC2 (Ollama + Whisper)"
echo "  [ ] Terminate old frontend EC2"
echo "  [ ] Terminate old Plan B API EC2"
echo ""
read -r -p "Type TERMINATE to acknowledge decommission complete: " CONFIRM
if [[ "$CONFIRM" != "TERMINATE" ]]; then
  echo "Aborted."
  exit 1
fi
echo "Step 8 complete."
