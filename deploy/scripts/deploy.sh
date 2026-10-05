#!/bin/bash
# deploy.sh — Deploy FleetGuard to a running EC2 instance
#
# Prerequisites:
#   - EC2 instance already provisioned (via Terraform)
#   - SSH key available
#   - Server IP exported as SERVER_IP
#
# Usage:
#   export SERVER_IP=54.x.x.x
#   export KEY_FILE=~/.ssh/fleetguard.pem
#   bash deploy/scripts/deploy.sh

set -euo pipefail

SERVER_IP="${SERVER_IP:?Set SERVER_IP to your EC2 public IP}"
KEY_FILE="${KEY_FILE:-~/.ssh/fleetguard.pem}"
APP_DIR="/opt/fleetguard"
SSH="ssh -i $KEY_FILE -o StrictHostKeyChecking=no ubuntu@$SERVER_IP"

echo ""
echo "=================================================="
echo "  FleetGuard — Deploying to $SERVER_IP"
echo "=================================================="

# ── Sync files ────────────────────────────────────────────────────────────────
echo ""
echo "[1/4] Syncing project files..."
rsync -az --progress \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'node_modules' \
  --exclude 'frontend/dist' \
  --exclude 'data/raw' \
  --exclude 'mlruns' \
  --exclude '.env' \
  . ubuntu@$SERVER_IP:$APP_DIR/

# ── Restart services ──────────────────────────────────────────────────────────
echo ""
echo "[2/4] Rebuilding and restarting services..."
$SSH << 'REMOTE'
  set -e
  cd /opt/fleetguard
  docker compose -f docker-compose.prod.yml build --parallel
  docker compose -f docker-compose.prod.yml up -d
REMOTE

# ── Seed DB (idempotent) ──────────────────────────────────────────────────────
echo ""
echo "[3/4] Seeding database (idempotent)..."
$SSH "cd $APP_DIR && docker compose -f docker-compose.prod.yml exec -T backend python database/docker_seed.py 2>&1" || true

# ── Health check ──────────────────────────────────────────────────────────────
echo ""
echo "[4/4] Running health check..."
sleep 8
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://$SERVER_IP/health" || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
  echo ""
  echo "=================================================="
  echo "  Deployment SUCCESSFUL"
  echo "=================================================="
  echo "  App:        http://$SERVER_IP"
  echo "  API Docs:   http://$SERVER_IP/api/docs"
  echo "  Grafana:    http://$SERVER_IP/grafana"
  echo "  Prometheus: http://$SERVER_IP:9090"
  echo "  Metrics:    http://$SERVER_IP/metrics"
  echo "=================================================="
else
  echo ""
  echo "[ERROR] Health check returned HTTP $HTTP_CODE"
  echo "Checking logs..."
  $SSH "cd $APP_DIR && docker compose -f docker-compose.prod.yml logs --tail=30 backend"
  exit 1
fi
