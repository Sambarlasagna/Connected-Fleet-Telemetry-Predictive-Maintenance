#!/bin/bash
# user_data.sh — EC2 bootstrap script for FleetGuard
# Runs once on first launch. Installs Docker, clones repo, starts the stack.

set -euo pipefail
exec > >(tee /var/log/fleetguard-bootstrap.log) 2>&1

echo "=== FleetGuard EC2 Bootstrap ==="
echo "Started: $(date)"

# ── System updates ────────────────────────────────────────────────────────────
apt-get update -y
apt-get install -y git curl unzip python3-pip awscli

# ── Docker ────────────────────────────────────────────────────────────────────
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu
systemctl enable docker
systemctl start docker

# ── Docker Compose v2 ─────────────────────────────────────────────────────────
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/v2.27.1/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# ── Clone the project ─────────────────────────────────────────────────────────
APP_DIR="/opt/fleetguard"
git clone https://github.com/Sambarlasagna/Connected-Fleet-Telemetry-Predictive-Maintenance.git "$APP_DIR"
cd "$APP_DIR"

# ── Write environment file ────────────────────────────────────────────────────
SERVER_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "localhost")

cat > "$APP_DIR/.env" << EOF
POSTGRES_PASSWORD=${postgres_password}
GRAFANA_PASSWORD=${grafana_password}
SERVER_HOST=$SERVER_IP
AWS_DEFAULT_REGION=${aws_region}
S3_BUCKET=${s3_bucket}
EOF

# ── Prometheus production config ──────────────────────────────────────────────
cat > "$APP_DIR/monitoring/prometheus/prometheus.prod.yml" << 'PROMEOF'
global:
  scrape_interval: 15s
  external_labels:
    environment: 'production'
    project: 'fleetguard'

scrape_configs:
  - job_name: 'fleetguard-api'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /metrics

  - job_name: 'fleetguard-fleet'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /api/metrics/fleet

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
PROMEOF

# ── Seed the database ─────────────────────────────────────────────────────────
# Wait for postgres to be ready, then seed
cat > /tmp/seed.sh << 'SEEDEOF'
#!/bin/bash
cd /opt/fleetguard
sleep 15  # give postgres time to init

docker compose -f docker-compose.prod.yml exec -T backend python database/docker_seed.py 2>&1 || true
echo "Seeding complete"
SEEDEOF
chmod +x /tmp/seed.sh

# ── Start the full stack ──────────────────────────────────────────────────────
cd "$APP_DIR"
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --build

# Run seed after stack is up
/tmp/seed.sh &

# ── Systemd service (auto-restart on reboot) ──────────────────────────────────
cat > /etc/systemd/system/fleetguard.service << SERVICEEOF
[Unit]
Description=FleetGuard Application
Requires=docker.service
After=docker.service network.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/fleetguard
ExecStart=/usr/local/lib/docker/cli-plugins/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/lib/docker/cli-plugins/docker-compose -f docker-compose.prod.yml down
TimeoutStartSec=300
User=ubuntu
EnvironmentFile=/opt/fleetguard/.env

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable fleetguard

echo ""
echo "=== Bootstrap Complete ==="
echo "Public IP:   $SERVER_IP"
echo "App URL:     http://$SERVER_IP"
echo "API Docs:    http://$SERVER_IP/api/docs"
echo "Grafana:     http://$SERVER_IP/grafana  (admin / ${grafana_password})"
echo "Prometheus:  http://$SERVER_IP:9090"
echo "Finished:    $(date)"
