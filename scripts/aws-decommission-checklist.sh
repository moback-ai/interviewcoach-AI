#!/usr/bin/env bash
# Print AWS decommission checklist (prod only). Does not change AWS.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOC="${ROOT}/docs/AWS_DECOMMISSION.md"

echo "=== InterviewCoach PROD — AWS removal checklist ==="
echo "Full doc: docs/AWS_DECOMMISSION.md"
echo ""
echo "TERMINATE (after 7 days stable):"
echo "  [ ] AI EC2 (Ollama + Whisper)"
echo "  [ ] Frontend EC2 (when CloudFront + S3 live)"
echo "  [ ] Old Plan B API EC2 (when new prod EC2 is stable)"
echo ""
echo "STOP / REMOVE on AWS:"
echo "  [ ] Whisper transcribe sidecar (port 5001)"
echo "  [ ] Ollama on AI EC2"
echo "  [ ] nginx frontend EC2 (CloudFront + S3 replaces it)"
echo ""
echo "SECRETS (interviewcoach/prod/app) — DELETE keys:"
echo "  OLLAMA_*  TRANSCRIBE_SERVICE_URL  WHISPER_*  ENABLE_AI_WARMUP"
echo ""
echo "SECRETS — ADD (see backend/secrets.prod.example.json):"
echo "  LLM_PROVIDER=bedrock  STT_PRIMARY=openrouter  STT_FALLBACK=amazon"
echo "  OPENROUTER_API_KEY  BEDROCK_CHAT_MODEL  S3_BUCKET  REDIS_URL"
echo ""
echo "SECURITY GROUPS — REMOVE rules:"
echo "  API → AI:11434  API → AI:5001"
echo ""
if [[ -f "$DOC" ]]; then
  echo "Open ${DOC} for complete steps."
fi
