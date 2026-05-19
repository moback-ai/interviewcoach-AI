#!/usr/bin/env bash
# Run on the backend EC2 host (e.g. ssh ubuntu@<backend-host> 'bash -s' < scripts/server-repair.sh)
set -euo pipefail

echo "=== InterviewCoach server repair ==="

echo "[1/5] Backend health (local)"
curl -fsS http://127.0.0.1:5000/api/health | python3 -m json.tool || {
  echo "Backend is not healthy on :5000. Check: pm2 status && pm2 logs backend --lines 80"
  pm2 status || true
}

echo "[2/5] PM2 backend"
if command -v pm2 >/dev/null 2>&1; then
  pm2 status || true
else
  echo "pm2 not installed"
fi

echo "[3/5] Ollama service"
if command -v ollama >/dev/null 2>&1; then
  if systemctl list-unit-files ollama.service >/dev/null 2>&1; then
    sudo systemctl enable ollama
    sudo systemctl restart ollama || sudo systemctl start ollama
    sleep 5
    systemctl is-active ollama || true
  else
    echo "Starting ollama serve in background (no systemd unit)"
    nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
    sleep 5
  fi
  curl -fsS http://127.0.0.1:11434/api/tags && echo "Ollama is reachable"
  ollama pull "${OLLAMA_MODEL:-llama3}" || true
else
  echo "Ollama not installed. Install with: curl -fsSL https://ollama.com/install.sh | sh"
fi

echo "[4/5] Nginx (frontend host — skip if this is backend-only)"
if command -v nginx >/dev/null 2>&1; then
  sudo nginx -t
  sudo systemctl reload nginx || sudo systemctl restart nginx
fi

echo "[5/5] Final API health"
curl -fsS http://127.0.0.1:5000/api/health | python3 -m json.tool
echo "=== Repair complete ==="
