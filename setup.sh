#!/bin/bash
# ============================================================
# InterviewCoach - Full EC2 Setup Script
# Run once on a fresh Ubuntu 22.04 EC2 instance
# Usage: bash setup.sh
# ============================================================
set -e

echo "============================================"
echo "  InterviewCoach - EC2 Setup"
echo "============================================"

# ── System packages ───────────────────────────────────────────
echo "[1/8] Installing system packages..."
sudo apt update -q
sudo apt install -y \
    python3 python3-pip python3-venv \
    nginx ffmpeg git curl \
    postgresql-client \
    build-essential pkg-config \
    libpq-dev libsndfile1 libgl1-mesa-glx \
    nodejs npm

# ── Node / PM2 ────────────────────────────────────────────────
echo "[2/8] Installing Node/PM2..."
sudo npm install -g pm2 n
sudo n 22
hash -r
pm2 startup systemd -u ubuntu --hp /home/ubuntu | tail -1 | sudo bash

# ── Storage dirs ──────────────────────────────────────────────
echo "[3/8] Creating storage directories..."
sudo mkdir -p /apps/storage/{resumes,audio,general}
sudo chown -R ubuntu:ubuntu /apps/storage
chmod -R 755 /apps/storage

# ── Frontend build dir ────────────────────────────────────────
sudo mkdir -p /var/www/interview
sudo chown ubuntu:ubuntu /var/www/interview

# ── Python venv ───────────────────────────────────────────────
echo "[4/8] Creating Python virtual environment..."
cd /apps/backend
python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir -r requirements.txt

# ── Nginx ─────────────────────────────────────────────────────
echo "[5/8] Configuring Nginx..."
sudo bash -c 'cat > /etc/nginx/sites-available/interview << '"'"'NGINX'"'"'
server {
    listen 80;
    server_name _;

    # Frontend
    root /var/www/interview;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        client_max_body_size 200M;
    }

    # WebSocket for head tracking
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 300s;
    }

    # Local file storage (resumes, audio)
    location /storage/ {
        alias /apps/storage/;
        add_header Access-Control-Allow-Origin *;
        add_header Cache-Control "public, max-age=3600";
    }
}
NGINX'

sudo ln -sf /etc/nginx/sites-available/interview /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

# ── PM2 backend ───────────────────────────────────────────────
echo "[6/8] Starting backend with PM2..."
cd /apps/backend
pm2 delete backend 2>/dev/null || true
pm2 start "venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 --timeout 300 --worker-class eventlet app:app" \
    --name backend
pm2 save

# ── Frontend build ────────────────────────────────────────────
echo "[7/8] Building frontend..."
cd /apps/frontend
npm install --legacy-peer-deps
npm run build
cp -r dist/* /var/www/interview/
sudo systemctl reload nginx

# ── Done ─────────────────────────────────────────────────────
echo "[8/8] Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit /apps/backend/.env with your real values"
echo "  2. Run the DB schema: psql -h DB_IP -U interview_user -d interview_db -f /apps/backend/schema.sql"
echo "  3. Verify: curl http://localhost/api/health"
echo ""
echo "PM2 status:"
pm2 status
