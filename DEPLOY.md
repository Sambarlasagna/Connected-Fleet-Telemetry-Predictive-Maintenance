# FleetGuard — Cloud Deployment Guide

## Architecture

```
Internet → Nginx (:80) → FastAPI backend (:8000, internal)
                       → React frontend (:80, internal)
                       → Grafana (:3000, at /grafana)

Prometheus scrapes:
  backend:8000/metrics           (HTTP metrics)
  backend:8000/api/metrics/fleet (business metrics)
```

## Option A — Deploy to AWS EC2 with Terraform

### Prerequisites
- AWS CLI configured (`aws configure`)
- Terraform installed (`brew install terraform` or [terraform.io](https://terraform.io))
- EC2 key pair created in AWS console

### Steps

```bash
# 1. Initialize Terraform
cd deploy/terraform
terraform init

# 2. Preview what will be created
terraform plan -var="key_pair_name=your-key-pair-name"

# 3. Deploy (~2 minutes)
terraform apply -var="key_pair_name=your-key-pair-name"

# Terraform outputs:
#   public_ip    = "54.x.x.x"
#   public_url   = "http://54.x.x.x"
#   grafana_url  = "http://54.x.x.x/grafana"
#   ssh_command  = "ssh -i ..."
```

The EC2 user data script automatically:
- Installs Docker + Docker Compose
- Clones the repo
- Starts all services
- Seeds the database

### Wait ~3 minutes, then open: `http://<your-ip>`

---

## Option B — Deploy to Any Server Manually

```bash
# On the target server (Ubuntu 22.04+):
curl -fsSL https://get.docker.com | sh
git clone https://github.com/Sambarlasagna/Connected-Fleet-Telemetry-Predictive-Maintenance.git /opt/fleetguard
cd /opt/fleetguard

# Configure environment
cp .env.example .env
nano .env   # fill in passwords and SERVER_HOST

# Start everything
docker compose -f docker-compose.prod.yml up -d --build

# Seed database
docker compose -f docker-compose.prod.yml exec backend python database/docker_seed.py
```

---

## Option C — Push with deploy script

```bash
export SERVER_IP=54.x.x.x
export KEY_FILE=~/.ssh/your-key.pem
bash deploy/scripts/deploy.sh
```

---

## CI/CD (GitHub Actions)

Add these secrets in **Settings → Secrets → Actions**:

| Secret | Value |
|---|---|
| `EC2_HOST` | Your server's public IP |
| `EC2_SSH_KEY` | Contents of your `.pem` private key |
| `VITE_API_URL` | `http://your-ip/api` (optional) |

Every push to `main` → runs tests → builds images → deploys to EC2.

---

## Service URLs (once deployed)

| Service | URL |
|---|---|
| **React Dashboard** | `http://<ip>/` |
| **API Docs** | `http://<ip>/api/docs` |
| **Grafana** | `http://<ip>/grafana` · `admin / fleetguard` |
| **Prometheus** | `http://<ip>:9090` |
| **Metrics endpoint** | `http://<ip>/metrics` |

---

## Useful Commands

```bash
# Check all service statuses
docker compose -f docker-compose.prod.yml ps

# View backend logs
docker compose -f docker-compose.prod.yml logs -f backend

# Restart a single service
docker compose -f docker-compose.prod.yml restart backend

# Destroy AWS infrastructure
cd deploy/terraform && terraform destroy
```
