# FleetGuard — Real-Time Predictive Maintenance Platform

<div align="center">

![FleetGuard](https://img.shields.io/badge/FleetGuard-Predictive%20Maintenance-6366f1?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=flat-square&logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)
![Kafka](https://img.shields.io/badge/Apache%20Kafka-Streaming-231F20?style=flat-square&logo=apachekafka)
![PySpark](https://img.shields.io/badge/PySpark-Batch-E25A1C?style=flat-square&logo=apachespark)
![MLflow](https://img.shields.io/badge/MLflow-Tracking-0194E2?style=flat-square&logo=mlflow)
![Prometheus](https://img.shields.io/badge/Prometheus-Monitoring-E6522C?style=flat-square&logo=prometheus)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)
![AWS](https://img.shields.io/badge/AWS-EC2%20%2B%20S3-FF9900?style=flat-square&logo=amazonaws)

**A cloud-native, end-to-end predictive maintenance platform for connected vehicle fleets.**

*Kafka streaming → PySpark feature engineering → RandomForest ML → MLflow tracking → Prometheus observability → React dashboard*

</div>

---

## What It Does

FleetGuard monitors a fleet of vehicles in real time, ingesting sensor telemetry through Kafka, engineering features with PySpark, predicting mechanical failure risk with a trained RandomForest model, and surfacing everything through a live React dashboard. The system detects risk before failures happen and explains *why* using SHAP feature attribution.

A recruiter or engineer can open the dashboard and:
- See all 20 vehicles with live health status (🟢 Healthy → 🟡 At Risk → 🔴 Critical)
- Click any vehicle to see live telemetry charts and failure probability
- Understand the prediction via SHAP feature contribution bars
- Start a simulation and watch vehicles degrade in real time
- View ML experiment runs, model metrics, and the model registry
- Access Grafana dashboards tracking fleet health and API performance

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     React Dashboard (Vite)                       │
│          Fleet Overview · Vehicle Detail · ML Analytics          │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST API
┌───────────────────────────▼─────────────────────────────────────┐
│                    FastAPI Backend                               │
│   /fleet  /vehicles  /predictions  /simulation  /mlflow  /metrics│
└──────┬──────────────────┬──────────────────────┬────────────────┘
       │                  │                       │
┌──────▼──────┐   ┌───────▼──────┐      ┌────────▼────────┐
│  PostgreSQL  │   │  ML Model    │      │  Prometheus     │
│  telemetry   │   │  RandomForest│      │  + Grafana      │
│  predictions │   │  + SHAP      │      │  Observability  │
│  alerts      │   └──────────────┘      └─────────────────┘
└─────────────┘
       ▲
       │ writes
┌──────┴────────────────────────────────────────────────────────┐
│               Live Telemetry Pipeline                          │
│                                                               │
│  Vehicle Simulator ──► Kafka ──► Python Consumer             │
│       (20 vehicles)    (vehicle-telemetry)  │                 │
│       Scenarios:                            ▼                 │
│       - bearing_wear              Feature Engineering         │
│       - overheating                        │                  │
│       - electrical_fault                   ▼                  │
│       - sensor_drift              RF Prediction + SHAP        │
│                                           │                   │
│                                           ▼                   │
│                              PostgreSQL (telemetry + alerts)  │
└───────────────────────────────────────────────────────────────┘
       │
       │ (batch)
┌──────▼────────────────────────────────────────────────────────┐
│               PySpark Batch Pipeline                           │
│   CSV Export → Preprocessing → Feature Engineering            │
│       → Model Training → MLflow → Model Registry             │
│                                                               │
│   Automated via Airflow DAG (weekly retraining)               │
└───────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React 18 + Vite | Fleet dashboard, telemetry charts, SHAP viz |
| **API** | FastAPI 0.141 | REST endpoints, simulation control |
| **Database** | PostgreSQL 16 | Telemetry, predictions, alerts, machines |
| **Streaming** | Apache Kafka + kafka-python-ng | Real-time telemetry pipeline |
| **Big Data** | PySpark 3.5 | Batch feature engineering on historical data |
| **ML** | scikit-learn RandomForest | Failure probability prediction |
| **Explainability** | SHAP | Feature contribution explanations |
| **MLOps** | MLflow 3.x | Experiment tracking + model registry |
| **Orchestration** | Apache Airflow 2.9 | Automated weekly model retraining DAG |
| **Monitoring** | Prometheus + Grafana | Metrics, dashboards, alerting |
| **Containers** | Docker + Docker Compose | Full local + production stack |
| **Cloud** | AWS EC2 + S3 + IAM | Public deployment + telemetry archiving |
| **CI/CD** | GitHub Actions | Test → Build → Push to GHCR → Deploy to EC2 |
| **IaC** | Terraform | Reproducible AWS infrastructure |

---

## ML Model Performance

The RandomForest classifier is trained on 27 engineered features derived from 4 raw sensor signals (voltage, rotation, pressure, vibration) with 3h and 24h rolling window statistics:

| Metric | Score |
|---|---|
| **AUC-ROC** | **0.9762** |
| **F1 Score** | **0.8650** |
| **Precision** | **0.8084** |
| **Recall** | **0.9301** |

Training runs, hyperparameters, and metrics are tracked in MLflow. The hyperparameter sweep trains 5 configurations and automatically promotes the highest-AUC model to Production.

---

## Project Structure

```
.
├── frontend/                  # React dashboard (Vite + CSS)
│   └── src/
│       ├── pages/             # LandingPage, FleetDashboard, MachineDetail, AnalyticsPage
│       └── services/api.js    # API client
│
├── backend/                   # FastAPI application
│   └── app/
│       ├── routes/            # fleet, vehicles, predictions, simulation, mlflow, monitoring
│       ├── services/metrics.py# Prometheus custom metrics registry
│       └── main.py            # App + Prometheus middleware
│
├── simulator/                 # Vehicle telemetry simulator
│   ├── vehicle.py             # Vehicle model with degradation
│   ├── scenarios.py           # Fault scenarios (bearing_wear, overheating, ...)
│   └── runner.py              # Thread-based simulation controller
│
├── streaming/
│   ├── producer.py            # Kafka producer (simulator → vehicle-telemetry)
│   └── consumer.py            # Kafka consumer → feature eng → prediction → DB
│
├── spark/                     # PySpark batch pipeline
│   ├── preprocessing/         # Data cleaning + quality scoring
│   ├── feature_engineering/   # Rolling window features (3h, 24h)
│   └── batch_inference/       # Batch ML predictions
│
├── ml/
│   ├── training/
│   │   ├── train_with_mlflow.py     # Single training run
│   │   └── hyperparameter_sweep.py  # 5-config sweep + auto-promote
│   └── export_model.py        # Export model to disk
│
├── airflow/
│   ├── dags/fleetguard_retrain_dag.py  # 8-step retraining DAG
│   └── run_pipeline.py               # Standalone runner (no Airflow needed)
│
├── monitoring/
│   ├── prometheus/prometheus.yml      # Scrape config
│   └── grafana/
│       ├── dashboards/fleetguard.json # Pre-built dashboard
│       └── provisioning/             # Auto-provisioned datasource + dashboards
│
├── deploy/
│   ├── terraform/main.tf      # AWS VPC + EC2 + S3 + IAM
│   ├── nginx/nginx.prod.conf  # Reverse proxy config
│   └── scripts/deploy.sh      # Manual deploy script
│
├── .github/workflows/deploy.yml  # CI/CD pipeline
├── docker-compose.yml             # Local development stack
├── docker-compose.prod.yml        # Production stack
├── docker-compose.airflow.yml     # Airflow add-on stack
└── DEPLOY.md                      # Full deployment guide
```

---

## Quick Start

### Prerequisites
- Docker Desktop (running)
- Python 3.12
- Node.js 20

### ⚡ One-command start (Windows)

```powershell
.\start.ps1
```

That's it. It starts Docker services, backend, and frontend automatically — each in their own terminal window — and prints the URLs when ready.

```powershell
.\start.ps1          # start everything
.\start.ps1 -Reset   # wipe DB back to seed data, then start
.\start.ps1 -Stop    # shut down Docker services
```

> **First time?** Allow local scripts once:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

**URLs after startup:**

| Service | URL |
|---|---|
| Dashboard | http://localhost:5173 |
| API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

---

### Manual startup (alternative)

<details>
<summary>Expand manual steps</summary>

**1. Start infrastructure**
```bash
docker compose up -d postgres zookeeper kafka
```

**2. Start backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir . --reload-dir ..\simulator --reload-dir ..\streaming
```

**3. Start frontend**
```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

**4. (Optional) Start live simulation**

From the dashboard → click **Start Simulation** — or via API:
```bash
curl -X POST http://localhost:8000/api/simulation/start \
  -H "Content-Type: application/json" \
  -d '{"scenario": "bearing_wear", "speed": 2.0}'
```

</details>

---

## MLflow

Train and track experiments:

```bash
# Single training run
python ml/training/train_with_mlflow.py

# Hyperparameter sweep (5 configs, auto-promotes best)
python ml/training/hyperparameter_sweep.py

# Start MLflow UI
mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --port 5000
# → http://localhost:5000
```

---

## Retraining Pipeline (Airflow)

```bash
# Run the full pipeline locally (no Airflow required)
python airflow/run_pipeline.py --skip-spark --min-rows 100

# Dry-run (just check data freshness)
python airflow/run_pipeline.py --dry-run

# With Docker Airflow (full DAG)
docker compose -f docker-compose.yml -f docker-compose.airflow.yml up -d
# → http://localhost:8080  (admin / fleetguard)
```

Pipeline steps:
1. **Data freshness** — skip if < 500 new rows
2. **Export** — PostgreSQL → CSV
3. **PySpark preprocessing** — clean + DQ score
4. **PySpark feature engineering** — 3h + 24h rolling windows
5. **Baseline training** — log to MLflow
6. **Hyperparameter sweep** — 4 more configs
7. **Promote best** — highest AUC → Production stage
8. **Summary** — JSON report to `data/reports/`

---

## Monitoring

```bash
# Prometheus metrics
open http://localhost:8000/metrics          # raw text
open http://localhost:8000/api/metrics/fleet/json  # JSON snapshot

# Start monitoring stack
docker compose up -d prometheus grafana

# Grafana dashboard
open http://localhost:3000  # admin / fleetguard
```

Tracked metrics:
- `fleetguard_machines_by_risk{risk_level}` — distribution
- `fleetguard_avg_failure_probability` — fleet average
- `fleetguard_critical_machines` — count
- `fleetguard_active_alerts` — unresolved
- `fleetguard_simulation_ticks_total` — pipeline throughput
- `http_request_duration_seconds` — API latency histogram

---

## Deploy to AWS

```bash
cd deploy/terraform
terraform init
terraform apply -var="key_pair_name=your-key"
# → http://<elastic-ip> (live in ~3 minutes)
```

Full guide: [`DEPLOY.md`](DEPLOY.md)

---

## Demo Scenario

The full journey a user experiences:

1. Open the dashboard → see 20 vehicles with health status
2. Click **Start Simulation** → choose `bearing_wear` scenario
3. Watch Vehicle 3 → voltage drops, vibration rises
4. Risk badge flips: 🟢 → 🟡 → 🔴
5. Click the vehicle → see live telemetry charts
6. View **failure probability** updating every second
7. Click **Why is this risky?** → SHAP bars show `vibration_std3h` and `volt_mean3h` as top drivers
8. Open **ML Analytics** → see AUC 0.9762, all MLflow runs, model version in Production
9. Check Grafana → see API latency, machine distribution, Kafka throughput in real time

---

## License

MIT — see [LICENSE](LICENSE)
