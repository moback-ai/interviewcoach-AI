#!/usr/bin/env bash
# Local / CI security scan — Gitleaks, Trivy, Semgrep only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

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

install_tools
log "Security scan (Gitleaks · Trivy · Semgrep)"

run_check "Gitleaks" scan_gitleaks
run_check "Trivy" scan_trivy
run_check "Semgrep" scan_semgrep

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
