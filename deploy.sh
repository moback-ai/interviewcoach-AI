#!/bin/bash
# ============================================================
# InterviewCoach - Deploy Script
# Run after every code update
# Usage: bash deploy.sh
# ============================================================
set -e

echo "=== Deploying InterviewCoach ==="

# Backend
echo "[1/3] Restarting backend..."
cd /apps/backend
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt -q
pm2 restart backend
echo "Backend restarted"

# Frontend
echo "[2/3] Building frontend..."
cd /apps/frontend
npm install --legacy-peer-deps -q
npm run build
cp -r dist/* /var/www/interview/
echo "Frontend deployed"

# Nginx
echo "[3/3] Reloading Nginx..."
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "=== Deploy complete ==="
curl -s http://localhost/api/health
echo ""
pm2 status
