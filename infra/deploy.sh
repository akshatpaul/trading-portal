#!/usr/bin/env bash
# deploy.sh — Run LOCALLY to push code to EC2 and restart services
# Usage: ./infra/deploy.sh <EC2_PUBLIC_IP> <PATH_TO_PEM_KEY>
# Example: ./infra/deploy.sh 13.233.100.50 ~/.ssh/trading-key.pem
set -euo pipefail

EC2_IP="${1:?Usage: deploy.sh <EC2_IP> <PEM_KEY>}"
PEM_KEY="${2:?Usage: deploy.sh <EC2_IP> <PEM_KEY>}"
REMOTE_USER="ubuntu"
REMOTE_DIR="/opt/trading-portal"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Building React frontend..."
cd "$ROOT/frontend" && npm run build
cd "$ROOT"

echo "==> Syncing code to EC2 ($EC2_IP)..."
rsync -avz --progress \
  --exclude 'venv' \
  --exclude 'node_modules' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'frontend/.vite' \
  --exclude '.env' \
  -e "ssh -i $PEM_KEY -o StrictHostKeyChecking=no" \
  "$ROOT/" "$REMOTE_USER@$EC2_IP:$REMOTE_DIR/"

echo "==> Installing dependencies + restarting services on EC2..."
ssh -i "$PEM_KEY" "$REMOTE_USER@$EC2_IP" bash <<'ENDSSH'
  set -euo pipefail
  cd /opt/trading-portal

  # Python venv
  if [ ! -d venv ]; then
    echo "--> Creating Python venv..."
    python3.12 -m venv venv
  fi

  echo "--> Installing Python dependencies..."
  venv/bin/pip install -q pandas-ta --no-deps
  venv/bin/pip install -q -r backend/requirements.txt

  # Systemd service
  echo "--> Installing systemd service..."
  sudo cp infra/trading-backend.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable trading-backend
  sudo systemctl restart trading-backend

  # Nginx
  echo "--> Configuring nginx..."
  sudo cp infra/nginx.conf /etc/nginx/sites-available/trading-portal
  sudo ln -sf /etc/nginx/sites-available/trading-portal /etc/nginx/sites-enabled/trading-portal
  sudo rm -f /etc/nginx/sites-enabled/default
  sudo nginx -t && sudo systemctl reload nginx

  echo "==> Deploy complete!"
  echo "    Backend status:"
  sudo systemctl status trading-backend --no-pager -l | head -20
ENDSSH

echo ""
echo "==> Done! Site live at: https://alt.akshatpaul.com"
