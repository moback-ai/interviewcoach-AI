#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Frontend lint + audit + build guard"
(
  cd frontend
  npm ci --legacy-peer-deps
  npm run lint
  npm audit --audit-level=high
  echo "VITE_API_BASE_URL=/api" > .env
  echo "VITE_STORAGE_URL=/storage" >> .env
  npm run build
  bash ../scripts/verify-frontend-login-bundle.sh dist
)

echo "==> Backend pip-audit + bandit"
python3 -m pip install --upgrade pip >/dev/null
pip install -r backend/requirements.txt bandit pip-audit >/dev/null
bash scripts/pip-audit-production.sh
bandit -c .github/bandit.yml -r backend

echo "==> All local security checks passed."
