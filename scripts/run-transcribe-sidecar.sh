#!/usr/bin/env bash
# Run a minimal Flask app exposing /api/internal/transcribe-audio on port 5001.
# On API host set: TRANSCRIBE_SERVICE_URL=http://<this-host>:5001
#                   TRANSCRIBE_INTERNAL_TOKEN=<same token in both .env files>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
export FLASK_APP=app.py
export PORT="${TRANSCRIBE_SIDECAR_PORT:-5001}"
exec python -c "
from app import app
app.run(host='0.0.0.0', port=int('${PORT}'), threaded=True)
"
