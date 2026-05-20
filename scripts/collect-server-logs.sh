#!/usr/bin/env bash
# Collect multi-server logs onto the API host under /apps/logs/server/{DB,FRONTEND,BACKEND,AI}.
# Intended for cron on the API instance every 5–15 minutes.
#
# Prereqs on API host: deploy key at ~/.ssh/interviewcoach-deploy.pem
#   (run scripts/setup-ssh-key-from-aws.sh once), and FRONTEND_PUBLIC_IP / AI_PUBLIC_IP
#   in the environment or /apps/backend/.env.
set -euo pipefail

if [[ -f /apps/backend/.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /apps/backend/.env
  set +a
fi

LOG_ROOT="${LOG_ROOT:-/apps/logs}"
SERVER_DIR="${SERVER_DIR:-$LOG_ROOT/server}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/interviewcoach-deploy.pem}"
SSH_USER="${SSH_USER:-ubuntu}"
FRONTEND_IP="${FRONTEND_PUBLIC_IP:-${FRONTEND_IP:-}}"
AI_IP="${AI_PUBLIC_IP:-${AI_IP:-}}"
BACKEND_DIR="$SERVER_DIR/BACKEND"
FRONTEND_DIR="$SERVER_DIR/FRONTEND"
AI_DIR="$SERVER_DIR/AI"
DB_DIR="$SERVER_DIR/DB"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKEND_DIR" "$FRONTEND_DIR" "$AI_DIR" "$DB_DIR"

ssh_cmd() {
  local host="$1"
  shift
  ssh -i "$SSH_KEY" -o BatchMode=yes -o ConnectTimeout=12 -o StrictHostKeyChecking=accept-new \
    "${SSH_USER}@${host}" "$@"
}

copy_remote_file() {
  local host="$1"
  local remote_path="$2"
  local dest_path="$3"
  if ssh_cmd "$host" "test -r '$remote_path'"; then
    ssh_cmd "$host" "cat '$remote_path'" >"$dest_path"
  fi
}

# ── BACKEND (local API host) ─────────────────────────────────────────────────
for pattern in backend-error.log backend-out.log; do
  src="/home/ubuntu/.pm2/logs/$pattern"
  if [[ -r "$src" ]]; then
    tail -n 2000 "$src" >"$BACKEND_DIR/$pattern"
  fi
done

if command -v journalctl >/dev/null 2>&1; then
  journalctl -u gunicorn --no-pager -n 1500 >"$BACKEND_DIR/gunicorn-journal.log" 2>/dev/null \
    || journalctl --no-pager -n 1500 >"$BACKEND_DIR/system-journal.log" 2>/dev/null \
    || true
fi

touch "$BACKEND_DIR/api-failures.log"

# ── FRONTEND (nginx via SSH) ─────────────────────────────────────────────────
if [[ -n "$FRONTEND_IP" && -r "$SSH_KEY" ]]; then
  copy_remote_file "$FRONTEND_IP" /var/log/nginx/access.log "$FRONTEND_DIR/nginx-access.log" || true
  copy_remote_file "$FRONTEND_IP" /var/log/nginx/error.log "$FRONTEND_DIR/nginx-error.log" || true
fi

# ── AI (ollama journal / nginx if present) ───────────────────────────────────
if [[ -n "$AI_IP" && -r "$SSH_KEY" ]]; then
  ssh_cmd "$AI_IP" "journalctl -u ollama --no-pager -n 2000 2>/dev/null || journalctl --no-pager -n 2000" \
    >"$AI_DIR/ollama-journal.log" 2>/dev/null || true
  copy_remote_file "$AI_IP" /var/log/nginx/access.log "$AI_DIR/nginx-access.log" || true
  copy_remote_file "$AI_IP" /var/log/nginx/error.log "$AI_DIR/nginx-error.log" || true
fi

# ── DB snapshot (written from API host DB connection) ───────────────────────
if [[ -n "${DB_HOST:-}" && -n "${DB_NAME:-}" && -n "${DB_USER:-}" ]]; then
  PGPASSWORD="${DB_PASSWORD:-}" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -Atqc \
    "SELECT 'users=' || count(*) FROM users;" >"$DB_DIR/db-snapshot.log" 2>/dev/null || true
  {
    echo "# collected_at=$TIMESTAMP"
    PGPASSWORD="${DB_PASSWORD:-}" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -Atqc \
      "SELECT coalesce(state, 'unknown') || '=' || count(*) FROM pg_stat_activity WHERE datname = current_database() GROUP BY state ORDER BY state;" \
      2>/dev/null || true
  } >>"$DB_DIR/db-snapshot.log" 2>/dev/null || true
fi

# ── Metrics snapshot (local API host only; live UI uses /api/admin/metrics) ──
METRICS_DIR="$SERVER_DIR/METRICS"
mkdir -p "$METRICS_DIR"
if [[ -x /apps/backend/venv/bin/python3 && -f /apps/backend/current/common/host_metrics.py ]]; then
  /apps/backend/venv/bin/python3 - <<'PY' >"$METRICS_DIR/latest.json" 2>/dev/null || true
import json, os, sys, time
sys.path.insert(0, "/apps/backend/current")
from common.host_metrics import collect_linux_metrics
print(json.dumps({
    "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "hosts": [collect_linux_metrics("BACKEND", os.environ.get("BACKEND_HOST", "api"))],
}))
PY
fi

cat <<EOF
collect-server-logs completed at $TIMESTAMP
server_dir=$SERVER_DIR
frontend_ip=${FRONTEND_IP:-unset}
ai_ip=${AI_IP:-unset}
EOF
