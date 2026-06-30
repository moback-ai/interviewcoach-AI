#!/usr/bin/env bash
# Full Plan B optimization under ~$550/month (run from repo)
#
#   ./optimize-550.sh              # preview
#   ./optimize-550.sh --apply      # infra already done + budget alert
#   ./optimize-550.sh --apply --split-api   # also split API/Ollama (recommended)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY=0
SPLIT=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --split-api) SPLIT=1 ;;
  esac
done

chmod +x "${SCRIPT_DIR}"/*.sh

echo "=== Step 1: Plan B infra (RDS medium, frontend small) ==="
if [[ "$APPLY" -eq 1 ]]; then
  "${SCRIPT_DIR}/plan-b-setup.sh" --apply ${SPLIT:+--split-api}
else
  "${SCRIPT_DIR}/plan-b-setup.sh" ${SPLIT:+--split-api}
fi

if [[ "$SPLIT" -eq 1 && "$APPLY" -eq 1 ]]; then
  echo "=== Step 2: Bootstrap API server ==="
  "${SCRIPT_DIR}/bootstrap-api-server.sh" --apply
  echo "=== Step 3: Point nginx to API ==="
  "${SCRIPT_DIR}/update-frontend-nginx.sh" --apply
  echo "=== Step 4: Ollama-only on AI box ==="
  ssh -i "${SSH_KEY:-$HOME/.ssh/interviewcoach-deploy.pem}" -o StrictHostKeyChecking=accept-new \
    "ubuntu@${AI_PUBLIC_IP:-13.200.28.73}" 'pm2 delete backend 2>/dev/null || true; pm2 save; systemctl is-active ollama'
fi

echo "=== Step 5: Secrets + backend env ==="
"${SCRIPT_DIR}/apply-backend-env.sh" $([[ "$APPLY" -eq 1 ]] && echo --apply)

echo "=== Step 6: Budget alert \$550 ==="
"${SCRIPT_DIR}/set-budget-alert.sh" $([[ "$APPLY" -eq 1 ]] && echo --apply)

cat <<'EOF'

--- Still recommended (not AWS) ---
• GitHub Manual Deploy (frontend + backend) after PR merges
• Compress interviewer images; lazy-load on /interview

--- Capacity under $550 ---
• ~100 logins at once (RDS medium + rate-limit tuning)
• ~10–15 concurrent live interviews (not 100 parallel AI)

EOF
