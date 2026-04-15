#!/bin/bash
# ============================================================
# InterviewCoach - Database Setup Script
# Run on the PostgreSQL server (EC2 #2 or local)
# Usage: bash db_setup.sh
# ============================================================
set -e

DB_NAME="interview_db"
DB_USER="interview_user"
DB_PASS="CHANGE_THIS_STRONG_PASSWORD"

echo "=== Setting up PostgreSQL ==="

# Install PostgreSQL if not present
if ! command -v psql &> /dev/null; then
    sudo apt update -q
    sudo apt install -y postgresql postgresql-contrib
fi

sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create user and database
echo "[1/3] Creating database user and database..."
sudo -u postgres psql << SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';
  END IF;
END
\$\$;

SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\gexec

GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

# Run schema
echo "[2/3] Running schema..."
PGPASSWORD="${DB_PASS}" psql -U "${DB_USER}" -d "${DB_NAME}" -f /apps/backend/schema.sql
echo "Schema applied"

# Allow connections from backend server
echo "[3/3] Configuring PostgreSQL access..."
PG_CONF=$(sudo -u postgres psql -t -c "SHOW config_file;" | tr -d ' ')
PG_HBA=$(dirname "$PG_CONF")/pg_hba.conf

# Allow all private IPs (adjust if needed)
echo "host    ${DB_NAME}    ${DB_USER}    10.0.0.0/8    md5" | sudo tee -a "$PG_HBA"
echo "host    ${DB_NAME}    ${DB_USER}    172.16.0.0/12    md5" | sudo tee -a "$PG_HBA"

# Listen on all interfaces
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" "$PG_CONF"

sudo systemctl restart postgresql

echo ""
echo "=== Database ready ==="
echo "Host:     $(hostname -I | awk '{print $1}')"
echo "Database: ${DB_NAME}"
echo "User:     ${DB_USER}"
echo "Test:     PGPASSWORD='${DB_PASS}' psql -U ${DB_USER} -d ${DB_NAME} -c '\dt'"
