from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from fastapi import Depends
from app.database.connection import get_db
from app.models.schemas import FleetOverview, AlertResponse
from sqlalchemy import text

router = APIRouter()


@router.get("/fleet", response_model=FleetOverview)
def get_fleet_overview(db: Session = Depends(get_db)):
    """Fleet-wide summary stats and recent critical alerts."""

    counts = db.execute(text("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN risk_level = 'healthy'  THEN 1 ELSE 0 END) AS healthy_count,
            SUM(CASE WHEN risk_level = 'at_risk'  THEN 1 ELSE 0 END) AS at_risk_count,
            SUM(CASE WHEN risk_level = 'critical' THEN 1 ELSE 0 END) AS critical_count,
            AVG(failure_probability) AS avg_risk
        FROM machines
    """)).fetchone()

    alerts_rows = db.execute(text("""
        SELECT m.machine_id, m.machine_name, m.risk_level, m.failure_probability
        FROM machines m
        WHERE m.risk_level IN ('critical', 'at_risk')
        ORDER BY m.failure_probability DESC
        LIMIT 10
    """)).fetchall()

    alert_messages = {
        "critical": "High failure risk detected.",
        "at_risk":  "Abnormal sensor readings observed.",
    }

    alerts = [
        AlertResponse(
            machine_id=r.machine_id,
            machine_name=r.machine_name,
            risk_level=r.risk_level,
            failure_probability=r.failure_probability,
            message=alert_messages.get(r.risk_level, ""),
        )
        for r in alerts_rows
    ]

    return FleetOverview(
        total=counts.total or 0,
        healthy_count=counts.healthy_count or 0,
        at_risk_count=counts.at_risk_count or 0,
        critical_count=counts.critical_count or 0,
        avg_risk=round(float(counts.avg_risk or 0), 4),
        recent_alerts=alerts,
    )
