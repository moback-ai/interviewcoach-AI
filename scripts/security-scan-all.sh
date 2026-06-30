#!/usr/bin/env bash
# One-step security scan (logs internal; summary only).
# quick = PR (~2-3 min) | full = + Playwright smoke
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="${SECURITY_SCAN_PROFILE:-quick}"
LOG_DIR="$(mktemp -d)"
FAILED=()

log() { printf '%s\n' "$*" >&2; }

run_check() {
  local name="$1"
  shift
  log "  · $name"
  if "$@" >"$LOG_DIR/${name// /_}.log" 2>&1; then
    return 0
  fi
  FAILED+=("$name")
  return 0
}

install_tools() {
  log "Preparing scanners…"
  if ! command -v gitleaks >/dev/null 2>&1; then
    curl -sSfL https://github.com/gitleaks/gitleaks/releases/download/v8.24.2/gitleaks_8.24.2_linux_x64.tar.gz \
      | tar -xz -C /usr/local/bin gitleaks 2>/dev/null || true
  fi
  if ! command -v trivy >/dev/null 2>&1; then
    mkdir -p "$HOME/.local/bin"
    curl -fsSL -o /tmp/trivy.tar.gz \
      https://github.com/aquasecurity/trivy/releases/download/v0.70.0/trivy_0.70.0_Linux-64bit.tar.gz
    tar -xzf /tmp/trivy.tar.gz -C "$HOME/.local/bin" trivy
    export PATH="$HOME/.local/bin:$PATH"
  fi
  if ! command -v semgrep >/dev/null 2>&1; then
    python3 -m pip install --quiet semgrep
  fi
}

scan_gitleaks() {
  gitleaks detect --source . --config .gitleaks.toml
}

scan_frontend() {
  cd "$ROOT/frontend"
  npm ci --legacy-peer-deps --silent
  npm run lint -- --max-warnings 0
  echo "VITE_API_BASE_URL=/api" > .env
  echo "VITE_STORAGE_URL=/storage" >> .env
  npm run build
  bash "$ROOT/scripts/verify-frontend-login-bundle.sh" dist
  cd "$ROOT"
}

scan_backend() {
  python3 -m pip install --quiet --upgrade pip
  pip install --quiet -r backend/requirements.txt pytest
  python3 -m pytest backend/tests/ -q
}

scan_trivy() {
  trivy fs . \
    --severity CRITICAL,HIGH \
    --exit-code 1 \
    --skip-dirs backend/Piper,frontend/node_modules,frontend/dist,.git \
    --ignorefile .trivyignore \
    --format table
}

scan_semgrep() {
  semgrep scan --config p/ci --error
}

scan_playwright() {
  cd "$ROOT/frontend"
  npx playwright install chromium --with-deps >/dev/null
  npm run preview -- --host 127.0.0.1 --port 4173 &
  local pid=$!
  for _ in $(seq 1 45); do
    curl -fsS http://127.0.0.1:4173/login >/dev/null && break
    sleep 2
  done
  CI=true PLAYWRIGHT_BASE_URL=http://127.0.0.1:4173 npm run test:e2e
  kill "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
  cd "$ROOT"
}

install_tools
log "Security scan ($PROFILE)"

run_check "Gitleaks" scan_gitleaks
run_check "Frontend" scan_frontend
run_check "Backend" scan_backend
run_check "Trivy" scan_trivy
run_check "Semgrep" scan_semgrep

if [ "$PROFILE" = "full" ]; then
  run_check "Playwright" scan_playwright
fi

if [ "${#FAILED[@]}" -gt 0 ]; then
  log ""
  log "FAILED: ${FAILED[*]}"
  for name in "${FAILED[@]}"; do
    log "--- $name ---"
    sed -n '1,50p' "$LOG_DIR/${name// /_}.log" >&2 || true
  done
  echo "::error::Security scan failed (${#FAILED[@]} check(s))."
  exit 1
fi

log "All security checks passed."
