# FleetGuard — Deployment Plan

## 🎯 Goal

Turn **Connected Fleet Telemetry** from a local ML project into a publicly accessible, interactive predictive-maintenance platform.

A user should be able to open a public URL and:

- View overall fleet health
- View individual vehicles
- Inspect live telemetry
- See failure probability
- Understand why a vehicle is at risk (explainability)
- Start a simulated fleet
- Watch telemetry change in real time
- See predictions update live
- View historical fleet analytics

The project should demonstrate a complete production-style ML system:

> **Data → Streaming → Processing → ML → MLOps → API → Cloud → Monitoring → Dashboard**

---

# 🏗️ Final Architecture

```
                         ┌──────────────────────┐
                         │    Public Website     │
                         │    React Dashboard    │
                         └──────────┬────────────┘
                                    │
                                    ▼
                            ┌───────────────┐
                            │    FastAPI    │
                            │   REST API    │
                            └───────┬───────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  │                 │                  │
                  ▼                 ▼                  ▼
            PostgreSQL          ML Model           MLflow
                                   │              Model Registry
                                   ▼
                                 SHAP
                             Explainability

============================================================

                  LIVE TELEMETRY PIPELINE

Vehicle Simulator
       │
       ▼
     Kafka
       │
       ▼
   Python Consumer
       │
       ├──────────────► AWS S3 (raw archive)
       │
       ▼
  Feature Engineering
       │
       ▼
  ML Prediction
       │
       ▼
  FastAPI / PostgreSQL
       │
       ▼
  React Dashboard

============================================================

               BATCH / RETRAINING PIPELINE

AWS S3 (historical data)
       │
       ▼
    PySpark
       │
  ┌────┴────┐
  │         │
  ▼         ▼
Clean    Feature Engineering
  │         │
  └────┬────┘
       ▼
  Model Training
       │
       ▼
    MLflow
       │
  ┌────┴────┐
  │         │
  ▼         ▼
Metrics  Model Registry
```

---

# ☁️ Infrastructure

```
AWS
 │
 ├── S3                  ← raw + processed telemetry
 │
 ├── EC2                 ← Docker Compose deployment
 │   ├── FastAPI
 │   ├── React (served via Nginx)
 │   ├── PostgreSQL
 │   ├── Kafka
 │   ├── Python Consumer
 │   ├── MLflow
 │   ├── Prometheus
 │   └── Grafana
 │
 └── IAM                 ← access control
```

Everything runs via **Docker Compose** on a single EC2 instance.
This is cost-effective, reproducible, and achieves the public URL goal.

> Kubernetes and Terraform are documented as optional extensions (see Phase 9+) and configs will be included in the repo, but are not required for the public deployment.

---

# 📦 Project Structure

```
fleetguard/
│
├── frontend/
│   ├── src/
│   ├── components/
│   ├── pages/
│   └── services/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/
│   │   ├── services/
│   │   ├── models/
│   │   └── database/
│   └── Dockerfile
│
├── ml/
│   ├── training/
│   ├── inference/
│   ├── preprocessing/
│   ├── features/
│   └── models/
│
├── streaming/
│   ├── producer/        ← vehicle simulator → Kafka
│   └── consumer/        ← Kafka → feature eng → prediction → DB
│
├── spark/
│   ├── preprocessing/
│   ├── feature_engineering/
│   └── batch_inference/
│
├── simulator/
│   ├── vehicle.py
│   └── scenarios.py
│
├── monitoring/
│   ├── prometheus/
│   └── grafana/
│
├── kubernetes/          ← optional extension (configs only)
│   ├── backend/
│   ├── frontend/
│   └── kafka/
│
├── terraform/           ← optional extension (IaC configs)
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
│
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

# 1️⃣ Landing Page

```
FleetGuard

AI-Powered Predictive Maintenance
for Connected Vehicle Fleets

Monitor vehicle health.
Detect potential failures.
Prevent unexpected downtime.

[ Explore Demo Fleet ]
```

---

# 2️⃣ Fleet Dashboard

```
Fleet Overview
────────────────────────────────────

Total Vehicles       24

🟢 Healthy           17
🟡 At Risk            5
🔴 Critical           2


Average Failure Risk
██████████░░░░░░      38%


Recent Alerts
────────────────────────────────────

🔴 VH-003
High engine temperature
Failure risk: 91.3%

🟡 VH-017
Abnormal vibration
Failure risk: 63.2%
```

---

# 3️⃣ Vehicle Detail Page

```
Vehicle: VH-003

Status: 🔴 CRITICAL

Failure Probability
██████████████████░░ 91.3%

────────────────────────────────────

Live Telemetry

Engine Temperature  ╱╲
              ─────╱──╲────────

RPM
        ────────╲───────╱─

Vibration
            ──────╱╲─────────

Oil Pressure
              ────────╲───────

────────────────────────────────────

Prediction

HIGH FAILURE RISK

Recommended Action:
Schedule maintenance inspection.
```

---

# 4️⃣ ML Explainability (SHAP)

Show the major factors driving the prediction.

```
Why is this vehicle at risk?

Engine Temperature      +31%
Vibration               +27%
Oil Pressure            +19%
RPM Instability         +12%
Other                   +11%
```

Implementation:

```
SHAP values
   ↓
Feature importance per vehicle
   ↓
FastAPI endpoint
   ↓
React Dashboard
```

---

# 5️⃣ Vehicle Simulator

Python simulator produces realistic telemetry per vehicle:

```
vehicle_id
timestamp
engine_temperature
rpm
oil_pressure
vibration
battery_voltage
fuel_consumption
speed
```

Each vehicle runs a scenario that progresses over time:
- Normal → gradual degradation
- Sudden faults
- Recovery

---

# 6️⃣ Simulation Scenarios

```
Simulation Control

Vehicles: 20

Scenario:

○ Normal Operation
○ Engine Degradation
○ Overheating
○ Excessive Vibration
○ Low Oil Pressure
○ Random Fault

Speed:

1x  2x  5x

[ START SIMULATION ]
```

The dashboard reacts in real time as the simulation runs.

---

# 7️⃣ Kafka Streaming

```
Vehicle Simulator
       │
       ▼
Kafka Producer
       │
       ▼
 vehicle-telemetry  (Kafka topic)
       │
       ▼
Python Consumer
       │
   ┌───┴───┐
   │       │
   ▼       ▼
AWS S3   Feature Engineering
(archive)      │
               ▼
          ML Prediction
               │
               ▼
          PostgreSQL
```

Example telemetry event:

```json
{
  "vehicle_id": "VH-003",
  "timestamp": "2026-09-11T18:30:00",
  "engine_temperature": 104.2,
  "rpm": 3200,
  "oil_pressure": 21.4,
  "vibration": 8.2
}
```

> **Note:** The real-time path uses a lightweight **Python consumer** (not PySpark) for low-latency predictions. PySpark is reserved for the batch/historical pipeline where it actually adds value.

---

# 8️⃣ PySpark — Batch Pipeline

PySpark handles historical and batch processing only.

```
AWS S3 (raw historical data)
    ↓
PySpark
    ↓
Cleaning + Validation
    ↓
Joins
    ↓
Window Features (3h / 24h rolling)
    ↓
Feature Dataset
    ↓
Model Training
```

Continue using existing:

- 3-hour rolling features
- 24-hour rolling features
- Sensor relationship features
- Failure labels
- Broadcast joins

This is where scale is genuinely demonstrated — 876,000 rows processed distributedly.

---

# 9️⃣ ML Model

Start with the existing Random Forest model (AUC-ROC = 0.97, Recall = 89.6%).

```
Telemetry Features
    ↓
Random Forest
    ↓
Failure Probability (0.0 → 1.0)
    ↓
Risk Level: Healthy / At Risk / Critical
```

Later, optionally compare:

```
Random Forest  vs  XGBoost  vs  LightGBM
```

Only if it meaningfully improves the model — not just to list another technology.

---

# 🔟 MLflow

Track every training run:

```
Training Run
    ↓
Parameters (hyperparameters, features, dataset version)
    ↓
Metrics (AUC, Precision, Recall, F1, confusion matrix)
    ↓
Artifacts (model file, feature importance plot)
    ↓
Model Registry
```

Registry structure:

```
MLflow Model Registry

fleet_failure_model
       │
       ├── v1
       ├── v2
       └── v3  ← production
```

FastAPI loads the production model directly from the MLflow artifact store.

---

# 1️⃣1️⃣ FastAPI Backend

```
GET  /api/fleet                         ← fleet overview
GET  /api/vehicles                      ← all vehicles
GET  /api/vehicles/{id}                 ← vehicle detail
GET  /api/vehicles/{id}/telemetry       ← recent telemetry
GET  /api/vehicles/{id}/prediction      ← current prediction + SHAP
GET  /api/alerts                        ← active alerts
GET  /api/analytics                     ← fleet-wide statistics

POST /api/simulation/start              ← start a simulation scenario
POST /api/simulation/stop               ← stop simulation
```

Example response:

```json
{
  "vehicle_id": "VH-003",
  "failure_probability": 0.913,
  "risk_level": "critical",
  "recommended_action": "Schedule maintenance inspection",
  "explanation": {
    "engine_temperature": 0.31,
    "vibration": 0.27,
    "oil_pressure": 0.19,
    "rpm_instability": 0.12
  }
}
```

---

# 1️⃣2️⃣ PostgreSQL

Store application-facing data:

```
vehicles          ← vehicle metadata
telemetry         ← recent telemetry (last N readings per vehicle)
predictions       ← historical predictions
alerts            ← active + past alerts
simulation_sessions ← simulation runs
```

Raw historical telemetry at scale lives in **AWS S3**, not PostgreSQL.
PostgreSQL only holds what the web app needs.

---

# 1️⃣3️⃣ Docker

Every service runs in a container.

```
docker-compose.yml
│
├── frontend      (React + Nginx)
├── backend       (FastAPI)
├── consumer      (Python Kafka consumer)
├── simulator     (vehicle simulator)
├── kafka         (+ zookeeper)
├── postgres
├── mlflow
├── prometheus
└── grafana
```

Local development:

```bash
docker compose up
```

The entire platform should be reproducible locally from a single command.

---

# 1️⃣4️⃣ Prometheus + Grafana

Expose application metrics from FastAPI:

```
prediction_requests_total
prediction_latency_seconds
api_requests_total
api_request_latency_seconds
kafka_messages_consumed_total
active_simulations
```

Grafana dashboards:

- **API**: requests/sec, latency, error rate
- **ML**: prediction volume, high-risk rate, inference latency
- **Streaming**: Kafka message rate, consumer lag
- **System**: CPU, memory, container health

---

# 1️⃣5️⃣ AWS Deployment

Target: **single EC2 instance running Docker Compose**.

```
EC2 Instance
│
├── docker-compose.yml
│   ├── FastAPI (behind Nginx)
│   ├── React (served by Nginx)
│   ├── PostgreSQL
│   ├── Kafka
│   ├── Consumer
│   ├── MLflow
│   ├── Prometheus
│   └── Grafana
│
└── Elastic IP → yourdomain.com

AWS S3
└── raw/ processed/ features/  (connected via boto3)
```

Services:
- **S3**: telemetry storage
- **EC2**: application compute
- **IAM**: access control
- **Route 53** (optional): custom domain

---

# 🌐 1️⃣6️⃣ Public URL

The final product has a public URL.

```
https://fleetguard.yourdomain.com
```

Public users need **nothing** installed:
- No AWS credentials
- No Python
- No Docker
- No Kafka

Everything is behind the web application.

---

# 👤 Public User Flow

```
User
 │
 ▼
fleetguard.yourdomain.com
 │
 ▼
Landing Page
 │
 ▼
[ Explore Demo Fleet ]
 │
 ▼
Fleet Dashboard  (20 vehicles, live status)
 │
 ├── Click vehicle  →  Telemetry charts + failure probability + SHAP
 │
 ├── Start Simulation  →  Vehicles degrade in real time  🟢→🟡→🔴
 │
 └── Analytics  →  Fleet-wide statistics + historical trends
```

---

# 🎮 Demo Mode

```
[ START DEMO SIMULATION ]
```

Triggers a predefined scenario:

```
20 vehicles, normal operation
↓
Vehicle 7 develops overheating
↓
Vehicle 12 develops vibration anomaly
↓
ML detects increasing risk
↓
Dashboard updates:
🟢 → 🟡 → 🔴
```

This makes the ML *visible* to the user instead of hidden behind an API.

---

# 🔐 Public Deployment Safety

Never expose:
- AWS credentials
- Database passwords
- MLflow credentials
- Internal service endpoints
- Terraform state

Use:
- Environment variables + Docker secrets
- AWS IAM roles
- Read-only public demo access
- API rate limiting
- Input validation
- CORS configuration

---

# 💰 Cost Strategy

Build in stages. Don't pay for cloud until the app works locally.

### Stage 1 — Local

```
docker compose up
```

Everything runs on your machine. Free.

### Stage 2 — Cheap Public Demo

```
EC2 t3.medium (~$30/month)
+ S3 (pennies)
+ Elastic IP
```

Full public URL. Real architecture. Affordable.

### Stage 3 — Optional Extensions (after core is live)

Only add these if time and budget allow:

```
Kubernetes (EKS)     ← scalable deployment
Airflow              ← proper pipeline orchestration
Terraform            ← IaC for reproducible infra
```

> The Kubernetes YAML and Terraform configs will be written and committed to the repo even if not actively deployed — this demonstrates the knowledge without the cost.

---

# 🚀 Development Phases

## Phase 1 — Product MVP

Build the visible product first.

- React dashboard (fleet overview, vehicle pages)
- FastAPI backend (endpoints)
- PostgreSQL (schema + seed data)
- Existing ML model served via FastAPI
- SHAP explainability

Goal:
```
User → Website → See fleet → Click vehicle → See prediction
```

---

## Phase 2 — Simulation

Add live simulation.

- Vehicle simulator (Python)
- Multiple vehicles with scenarios
- Real-time telemetry updates
- Dashboard reacts live

Goal:
```
Simulator → Backend → Dashboard updates in real time
```

---

## Phase 3 — Kafka Streaming

Wire up the streaming pipeline.

- Kafka producer (simulator → Kafka)
- Python consumer (Kafka → feature eng → prediction → DB)
- S3 archive of raw events

Goal:
```
Simulator → Kafka → Consumer → Prediction → Dashboard
```

---

## Phase 4 — PySpark Batch Pipeline

Demonstrate big data processing.

- PySpark historical processing on S3 data
- Reproduce existing feature engineering pipeline
- Generate training dataset from raw S3 data

Goal:
```
S3 raw data → PySpark → Feature dataset
```

---

## Phase 5 — MLflow

Add full MLOps tracking.

- MLflow experiment tracking
- Log all training runs (params, metrics, artifacts)
- Model Registry with versioning
- FastAPI loads production model from registry

Goal:
```
Training run → MLflow → Model Registry → FastAPI serves it
```

---

## Phase 6 — Docker

Containerize everything.

- Dockerfile for each service
- docker-compose.yml that runs the full stack
- Environment variable configuration

Goal:
```bash
docker compose up  # entire platform running locally
```

---

## Phase 7 — Monitoring

Add production observability.

- Prometheus metrics in FastAPI
- Grafana dashboards (API, ML, Kafka, system)

Goal:
```
FastAPI → Prometheus → Grafana dashboard
```

---

## Phase 8 — AWS Deployment

Deploy publicly.

- EC2 instance
- S3 buckets (raw, processed, features)
- IAM roles
- Deploy Docker Compose on EC2
- Configure domain / Elastic IP
- Public URL live

Goal:
```
fleetguard.yourdomain.com → working product
```

---

## Phase 9 — Optional: Kubernetes

Write Kubernetes manifests. Deploy to EKS if budget allows.

- Deployments + Services for each component
- ConfigMaps + Secrets
- Health checks + scaling configs
- Document in README as production scaling path

---

## Phase 10 — Optional: Terraform + Airflow

- Terraform: codify the AWS infrastructure (S3, EC2, IAM, networking)
- Airflow: replace manual retraining script with a proper DAG

Both are documented in the repo regardless of whether they're actively deployed.

---

# 🧪 Final Demo Scenario

A recruiter should be able to do this:

```
1. Open FleetGuard at the public URL

2. Click "Explore Demo"

3. See 20 simulated vehicles with health status

4. Click "Start Simulation"

5. Watch telemetry arrive in real time

6. Select a vehicle

7. See live telemetry charts

8. See failure probability updating

9. Watch risk change:
   🟢 Healthy → 🟡 At Risk → 🔴 Critical

10. Click "Why?"

11. See SHAP feature contributions

12. Open Analytics

13. See fleet-wide statistics and trends

14. See Prometheus/Grafana metrics (linked or embedded)
```

---

# 🏆 Project Description

> **FleetGuard — Real-Time Predictive Maintenance Platform**

A cloud-native predictive maintenance platform for connected vehicle fleets. The system ingests simulated vehicle telemetry through Kafka, processes fleet-scale historical data using PySpark on AWS S3, engineers temporal sensor features, and predicts mechanical failure risk using machine learning. Models are tracked and versioned with MLflow. Services are containerized with Docker and deployed on AWS EC2. Prometheus and Grafana provide production observability. A React dashboard and FastAPI backend expose real-time fleet health, vehicle telemetry, failure predictions, alerts, and SHAP-powered maintenance recommendations through a publicly accessible web application.

---

# ✅ Definition of Done

**Product**
- [ ] Public URL works
- [ ] React dashboard works
- [ ] Fleet overview with health status
- [ ] Individual vehicle pages with telemetry charts
- [ ] Failure probability displayed per vehicle
- [ ] SHAP feature explanations displayed

**Simulation**
- [ ] Vehicle simulator running
- [ ] Multiple fault scenarios working
- [ ] Dashboard updates in real time

**Streaming**
- [ ] Kafka pipeline working (simulator → consumer)
- [ ] S3 raw event archive working
- [ ] Real-time predictions flowing

**Big Data**
- [ ] PySpark batch pipeline processes S3 data
- [ ] Feature engineering reproduces existing pipeline
- [ ] Training dataset generated from raw data

**MLOps**
- [ ] MLflow tracking all training runs
- [ ] Model Registry with versioned models
- [ ] FastAPI loads model from MLflow registry

**Infrastructure**
- [ ] Docker Compose runs full stack locally
- [ ] PostgreSQL stores application data
- [ ] S3 stores raw + processed telemetry

**Monitoring**
- [ ] Prometheus metrics exposed
- [ ] Grafana dashboards working

**Deployment**
- [ ] EC2 instance running Docker Compose
- [ ] Public URL accessible without setup
- [ ] No secrets committed to GitHub

**Documentation**
- [ ] README with architecture diagram
- [ ] README with ML methodology + results
- [ ] README with deployment instructions
- [ ] README with screenshots / demo GIF

**Optional (repo artifacts only)**
- [ ] Kubernetes YAML manifests written
- [ ] Terraform configs written
- [ ] Airflow DAG written

---

# ⭐ Core Principle

Build in this order:

```
PRODUCT (working UI + API)
   ↓
SIMULATION (live telemetry)
   ↓
STREAMING (Kafka pipeline)
   ↓
BIG DATA (PySpark batch)
   ↓
MLOps (MLflow)
   ↓
CONTAINERS (Docker)
   ↓
MONITORING (Prometheus + Grafana)
   ↓
AWS DEPLOYMENT (EC2 + S3)
   ↓
PUBLIC URL
   ↓
OPTIONAL: Kubernetes / Airflow / Terraform
```

The end goal:

> **"I built a publicly accessible predictive-maintenance product whose underlying ML system uses Kafka, PySpark, AWS S3, MLflow, Docker, and production monitoring — and anyone can use it right now at this URL."**
