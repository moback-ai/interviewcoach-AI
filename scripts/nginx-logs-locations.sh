#!/usr/bin/env bash
# Emit nginx location blocks for /logs (requires BACKEND_PROXY_HOST in environment).
set -euo pipefail

BACKEND_PROXY_HOST="${BACKEND_PROXY_HOST:?BACKEND_PROXY_HOST is required}"

cat <<NGINX
    location ^~ /logs/api/ {
        proxy_pass http://${BACKEND_PROXY_HOST}/logs/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
    }

    location ^~ /logs/files/ {
        proxy_pass http://${BACKEND_PROXY_HOST}/logs/files/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
    }

    location ^~ /logs/ {
        try_files \$uri \$uri/ /logs/index.html;
    }

NGINX
