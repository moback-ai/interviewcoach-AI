#!/usr/bin/env bash
# Forward RDS PostgreSQL to localhost:5433 via the API EC2 host.
set -euo pipefail

LOCAL_PORT="${LOCAL_PORT:-5433}"
RDS_HOST="${RDS_HOST:-interviewcoach-db.clmm8cymmic9.ap-south-1.rds.amazonaws.com}"
SSH_HOST="${SSH_HOST:-interviewcoach-api}"

if lsof -ti:"$LOCAL_PORT" >/dev/null 2>&1; then
  echo "Port $LOCAL_PORT already in use (tunnel may be running)."
  exit 0
fi

echo "Starting tunnel localhost:$LOCAL_PORT -> $RDS_HOST:5432 via $SSH_HOST"
ssh -f -N -L "${LOCAL_PORT}:${RDS_HOST}:5432" "$SSH_HOST"
echo "Tunnel up. Use DB_HOST=127.0.0.1 DB_PORT=$LOCAL_PORT for local backend."
