"""
metrics.py — Custom Prometheus metrics for FleetGuard.

Exposes:
  - fleetguard_machines_by_risk        (gauge)   machines per risk level
  - fleetguard_avg_failure_probability (gauge)   fleet-wide avg failure prob
  - fleetguard_predictions_total       (counter) total ML predictions made
  - fleetguard_prediction_latency_ms   (histogram) inference latency
  - fleetguard_simulation_ticks_total  (counter) simulation ticks
  - fleetguard_simulation_running      (gauge)   1 if sim is running, else 0
  - fleetguard_kafka_messages_total    (counter) Kafka messages produced
  - fleetguard_api_errors_total        (counter) API errors by endpoint
  - fleetguard_critical_machines       (gauge)   machines at critical risk
  - fleetguard_active_alerts           (gauge)   unresolved alerts count
"""

from prometheus_client import Counter, Gauge, Histogram, REGISTRY

# ── Risk distribution ──────────────────────────────────────────────────────────
machines_by_risk = Gauge(
    "fleetguard_machines_by_risk",
    "Number of machines at each risk level",
    ["risk_level"],
)

avg_failure_probability = Gauge(
    "fleetguard_avg_failure_probability",
    "Fleet-wide average failure probability (0.0–1.0)",
)

critical_machines = Gauge(
    "fleetguard_critical_machines",
    "Number of machines currently at CRITICAL risk level",
)

active_alerts = Gauge(
    "fleetguard_active_alerts",
    "Number of unresolved alerts",
)

# ── ML Inference ──────────────────────────────────────────────────────────────
predictions_total = Counter(
    "fleetguard_predictions_total",
    "Total number of ML predictions made",
    ["path"],   # fast / shap
)

prediction_latency_ms = Histogram(
    "fleetguard_prediction_latency_ms",
    "ML inference latency in milliseconds",
    ["path"],
    buckets=[1, 2, 5, 10, 20, 50, 100, 200, 500, 1000],
)

# ── Simulation ────────────────────────────────────────────────────────────────
simulation_ticks_total = Counter(
    "fleetguard_simulation_ticks_total",
    "Total number of simulation ticks executed",
)

simulation_running = Gauge(
    "fleetguard_simulation_running",
    "1 if simulation is currently running, 0 otherwise",
)

simulation_speed = Gauge(
    "fleetguard_simulation_speed",
    "Current simulation speed multiplier",
)

# ── Kafka Streaming ───────────────────────────────────────────────────────────
kafka_messages_produced = Counter(
    "fleetguard_kafka_messages_total",
    "Total Kafka messages produced to vehicle-telemetry topic",
)

kafka_messages_consumed = Counter(
    "fleetguard_kafka_messages_consumed_total",
    "Total Kafka messages consumed and processed",
)

# ── API ───────────────────────────────────────────────────────────────────────
api_errors_total = Counter(
    "fleetguard_api_errors_total",
    "Total API errors by endpoint",
    ["endpoint", "status_code"],
)
