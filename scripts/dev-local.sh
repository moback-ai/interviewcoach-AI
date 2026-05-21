#!/usr/bin/env bash
# Local dev: backend (Python 3.12) + frontend (Vite)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY312="${PY312:-/opt/homebrew/bin/python3.12}"

if [[ ! -x "$PY312" ]]; then
  echo "Install Python 3.12: brew install python@3.12"
  exit 1
fi

cd "$ROOT/backend"
if [[ ! -d venv ]]; then
  "$PY312" -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
else
  source venv/bin/activate
fi

export FLASK_APP=app:app
export FLASK_DEBUG=1
bash "$(dirname "$0")/dev-db-tunnel.sh"
export DB_HOST=127.0.0.1 DB_PORT=5433
set -a && source .env && set +a
export DB_HOST=127.0.0.1 DB_PORT=5433
echo "Backend: http://127.0.0.1:5001 (Ctrl+C to stop)"
python -m flask run --host 127.0.0.1 --port 5001
