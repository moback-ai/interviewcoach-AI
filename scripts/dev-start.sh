#!/usr/bin/env bash
# Start DB tunnel, backend, and frontend for local development.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY312="${PY312:-/opt/homebrew/bin/python3.12}"

bash "$ROOT/scripts/dev-db-tunnel.sh"

mkdir -p "$ROOT/storage"/{resumes,audio,general} "$ROOT/logs"

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
export DB_HOST=127.0.0.1
export DB_PORT=5433
set -a
source .env
set +a
export DB_HOST=127.0.0.1
export DB_PORT=5433

echo "Starting backend on http://127.0.0.1:5001"
python -m flask run --host 127.0.0.1 --port 5001 &
BACKEND_PID=$!

cd "$ROOT/frontend"
echo "Starting frontend on http://127.0.0.1:5173"
npm run dev &
FRONTEND_PID=$!

trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null' EXIT

echo ""
echo "Local dev:"
echo "  Frontend: http://127.0.0.1:5173"
echo "  Backend:  http://127.0.0.1:5001/api/health"
echo "  DB tunnel: localhost:5433 -> RDS"
echo "Press Ctrl+C to stop."
wait
