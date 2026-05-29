#!/usr/bin/env bash
# Run on Ubuntu EC2 during deployment to refresh OS packages and Node tooling.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
NODE_MAJOR="${NODE_MAJOR:-24}"

echo "=== apt update / upgrade (targets Ubuntu 24.04 LTS) ==="
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  echo "Host OS: ${PRETTY_NAME:-unknown}"
fi
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
sudo apt-get install -y -qq \
  ca-certificates curl gnupg rsync nginx xz-utils \
  python3 python3-pip python3-venv \
  build-essential pkg-config libpq-dev

if [[ "${INSTALL_FFMPEG:-0}" == "1" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  FFMPEG_SCRIPT="${SCRIPT_DIR}/install-ffmpeg-8.sh"
  [[ -f "$FFMPEG_SCRIPT" ]] || FFMPEG_SCRIPT="/tmp/install-ffmpeg-8.sh"
  if [[ -f "$FFMPEG_SCRIPT" ]]; then
    bash "$FFMPEG_SCRIPT"
  else
    echo "WARN: install-ffmpeg-8.sh not found — skipping FFmpeg 8.x install"
  fi
fi

echo "=== Node.js ${NODE_MAJOR}.x + npm + pm2 ==="
if ! command -v node >/dev/null 2>&1 || ! node --version | grep -q "v${NODE_MAJOR}\\."; then
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | sudo -E bash -
  sudo apt-get install -y -qq nodejs
fi
# Avoid corepack enable on EC2 — it needs write access to /usr/local/bin (EACCES as ubuntu).
sudo npm install -g "npm@latest" pm2@latest

echo "Node $(node --version)"
echo "npm $(npm --version)"
if command -v pm2 >/dev/null 2>&1; then
  echo "pm2 $(pm2 --version)"
fi

if command -v nginx >/dev/null 2>&1; then
  sudo nginx -t
  sudo systemctl reload nginx || sudo systemctl restart nginx
fi

echo "=== Toolchain update complete ==="
