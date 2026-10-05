"""
monitoring.py — FleetGuard custom Prometheus metrics endpoint.

GET /api/metrics/fleet  → update + return fleet-level gauges
                          (consumed by Prometheus scraper every 15s)

Metrics exposed:
  fleetguard_machines_by_risk{risk_level}   — machines per risk level
  fleetguard_avg_failure_probability        — fleet avg failure prob
  fleetguard_critical_machines              — count at critical
  fleetguard_active_alerts                  — unresolved alerts
  fleetguard_simulation_running             — 1/0
  fleetguard_simulation_ticks_total         — cumulative ticks
  fleetguard_simulation_speed               — current speed multiplier
"""

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.database.connection import get_db
from app.services.metrics import (
    machines_by_risk, avg_failure_probability, critical_machines,
    active_alerts, simulation_running, simulation_ticks_total,
    simulation_speed,
)

router = APIRouter()


def _update_fleet_gauges(db: Session):
    """Pull latest state from DB and update all Prometheus gauges."""
    # Risk distribution
    rows = db.execute(text("""
        SELECT risk_level, COUNT(*) AS cnt
        FROM machines
        GROUP BY risk_level
    """)).fetchall()

    risk_counts = {"healthy": 0, "at_risk": 0, "critical": 0}
    for r in rows:
        risk_counts[r.risk_level] = r.cnt

    for level, count in risk_counts.items():
        machines_by_risk.labels(risk_level=level).set(count)

    critical_machines.set(risk_counts.get("critical", 0))

    # Avg failure probability
    avg_row = db.execute(text("SELECT AVG(failure_probability) FROM machines")).fetchone()
    avg_failure_probability.set(float(avg_row[0] or 0))

    # Active unresolved alerts
    alert_row = db.execute(text("SELECT COUNT(*) FROM alerts WHERE resolved = FALSE")).fetchone()
    active_alerts.set(int(alert_row[0] or 0))

    # Simulation state
    try:
        from simulator.runner import runner
        simulation_running.set(1 if runner.is_running else 0)
        simulation_speed.set(runner.speed if runner.is_running else 0)
        # Note: ticks counter is incremented in runner.py directly
    except Exception:
        pass


@router.get("/metrics/fleet", include_in_schema=False)
def fleet_metrics_endpoint(db: Session = Depends(get_db)):
    """
    Called by Prometheus every 15s.
    Updates fleet gauges from DB then returns all metrics as text.
    """
    _update_fleet_gauges(db)
    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@router.get("/metrics/fleet/json")
def fleet_metrics_json(db: Session = Depends(get_db)):
    """Human-readable JSON snapshot of current fleet metrics."""
    _update_fleet_gauges(db)

    risk_rows = db.execute(text("""
        SELECT risk_level, COUNT(*) AS cnt FROM machines GROUP BY risk_level
    """)).fetchall()
    avg_row = db.execute(text("SELECT AVG(failure_probability) FROM machines")).fetchone()
    alert_row = db.execute(text("SELECT COUNT(*) FROM alerts WHERE resolved = FALSE")).fetchone()
    telemetry_row = db.execute(text("SELECT COUNT(*) FROM telemetry")).fetchone()
    prediction_row = db.execute(text("SELECT COUNT(*) FROM predictions")).fetchone()

    try:
        from simulator.runner import runner
        sim_state = {
            "is_running": runner.is_running,
            "tick_count": runner.tick_count,
            "speed":      runner.speed,
            "scenario":   runner.scenario,
            "kafka_mode": runner.kafka_mode,
        }
    except Exception:
        sim_state = {"is_running": False}

    return {
        "fleet": {
            "risk_distribution": {r.risk_level: r.cnt for r in risk_rows},
            "avg_failure_probability": round(float(avg_row[0] or 0), 4),
            "active_alerts": int(alert_row[0] or 0),
            "total_telemetry_rows": int(telemetry_row[0] or 0),
            "total_predictions": int(prediction_row[0] or 0),
        },
        "simulation": sim_state,
        "prometheus_scrape_url": "http://localhost:8000/api/metrics/fleet",
        "grafana_url": "http://localhost:3000",
        "mlflow_url": "http://localhost:5000",
    }
