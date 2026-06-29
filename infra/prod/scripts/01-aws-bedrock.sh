#!/usr/bin/env bash
# Phase 1 (AWS) — Enable Bedrock models in ap-south-1 (run once, Monday morning).
set -euo pipefail

echo "=== Step 1: Bedrock model access ==="
echo "Console: AWS → Bedrock → Model access → Enable:"
echo "  - Amazon Nova Lite / Pro / Micro (APAC)"
echo "  - Anthropic Claude Haiku (optional fallback)"
echo ""
echo "CLI (if model access API enabled in account):"
echo "  aws bedrock list-foundation-models --region ap-south-1 --query 'modelSummaries[?contains(modelId,\`nova\`)].modelId'"
echo ""
echo "Request service quota increase for:"
echo "  - Converse requests per minute"
echo "  - Tokens per minute (Nova Lite)"
echo ""
echo "Done checklist item 1 when model access shows Enabled."
