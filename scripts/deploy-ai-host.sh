#!/usr/bin/env bash
# Refresh Ollama on the AI host (Plan B: dedicated c6i.2xlarge).
set -euo pipefail

OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:3b}"
OLLAMA_HEALTH_URL="${OLLAMA_HEALTH_URL:-http://127.0.0.1:11434/api/tags}"

if command -v ollama >/dev/null 2>&1; then
  echo "Pulling Ollama model: ${OLLAMA_MODEL}"
  ollama pull "${OLLAMA_MODEL}" || true
fi

if systemctl list-unit-files ollama.service >/dev/null 2>&1; then
  sudo systemctl enable ollama
  sudo systemctl restart ollama || sudo systemctl start ollama
  systemctl is-active ollama
elif command -v ollama >/dev/null 2>&1; then
  echo "No ollama systemd unit; ensuring serve is running"
  if ! curl -fsS --max-time 3 "${OLLAMA_HEALTH_URL}" >/dev/null 2>&1; then
    nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
    sleep 3
  fi
fi

echo "Ollama health:"
curl -fsS --max-time 15 "${OLLAMA_HEALTH_URL}" | head -c 2000 || {
  echo "Ollama health check failed: ${OLLAMA_HEALTH_URL}"
  exit 1
}
echo ""
echo "AI host deploy complete."
