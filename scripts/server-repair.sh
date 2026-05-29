#!/usr/bin/env bash
# Run on the backend EC2 host (e.g. ssh ubuntu@<backend-host> 'bash -s' < scripts/server-repair.sh)
set -euo pipefail

echo "=== InterviewCoach server repair ==="

echo "[1/6] ffmpeg 8.x (audio transcoding)"
REPAIR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "${REPAIR_DIR}/install-ffmpeg-8.sh"

echo "[2/6] Backend health (local)"
curl -fsS http://127.0.0.1:5000/api/health | python3 -m json.tool || {
  echo "Backend is not healthy on :5000. Check: pm2 status && pm2 logs backend --lines 80"
  pm2 status || true
}

echo "[3/6] PM2 backend"
if command -v pm2 >/dev/null 2>&1; then
  pm2 status || true
else
  echo "pm2 not installed"
fi

echo "[4/6] Ollama service"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:3b}"
if command -v ollama >/dev/null 2>&1; then
  if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    if systemctl list-unit-files ollama.service >/dev/null 2>&1; then
      sudo systemctl enable ollama
      sudo systemctl restart ollama || sudo systemctl start ollama
    else
      echo "Starting ollama serve in background (no systemd unit)"
      nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
    fi
    sleep 5
  fi
  if systemctl list-unit-files ollama.service >/dev/null 2>&1; then
    systemctl is-active ollama || true
  fi
  curl -fsS http://127.0.0.1:11434/api/tags && echo "" && echo "Ollama is reachable"
  if curl -fsS http://127.0.0.1:11434/api/tags | grep -q "\"name\":\"${OLLAMA_MODEL}"; then
    echo "Model ${OLLAMA_MODEL} already present — skipping pull"
  else
    echo "Pulling ${OLLAMA_MODEL}..."
    ollama pull "$OLLAMA_MODEL" || true
  fi
else
  echo "Ollama not installed. Install with: curl -fsSL https://ollama.com/install.sh | sh"
fi

echo "[5/6] Nginx (frontend host — skip if this is backend-only)"
if command -v nginx >/dev/null 2>&1; then
  sudo nginx -t
  sudo systemctl reload nginx || sudo systemctl restart nginx
fi

echo "[6/6] Final API health"
curl -fsS http://127.0.0.1:5000/api/health | python3 -m json.tool
echo "=== Repair complete ==="
