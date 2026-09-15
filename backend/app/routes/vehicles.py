from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from fastapi import Depends
from app.database.connection import get_db
from app.models.schemas import MachineBase, MachineDetail, TelemetryPoint
from sqlalchemy import text
from typing import List

router = APIRouter()


@router.get("/vehicles", response_model=List[MachineBase])
def list_machines(db: Session = Depends(get_db)):
    """All machines with current status."""
    rows = db.execute(text("""
        SELECT machine_id, machine_name, model, age, risk_level, failure_probability
        FROM machines
        ORDER BY failure_probability DESC
    """)).fetchall()

    return [
        MachineBase(
            machine_id=r.machine_id,
            machine_name=r.machine_name,
            model=r.model,
            age=r.age,
            risk_level=r.risk_level,
            failure_probability=r.failure_probability,
        )
        for r in rows
    ]


@router.get("/vehicles/{machine_id}", response_model=MachineDetail)
def get_machine(machine_id: int, db: Session = Depends(get_db)):
    """Single machine detail."""
    row = db.execute(text("""
        SELECT machine_id, machine_name, model, age, risk_level, failure_probability
        FROM machines
        WHERE machine_id = :mid
    """), {"mid": machine_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Machine not found")

    return MachineDetail(
        machine_id=row.machine_id,
        machine_name=row.machine_name,
        model=row.model,
        age=row.age,
        risk_level=row.risk_level,
        failure_probability=row.failure_probability,
    )


@router.get("/vehicles/{machine_id}/telemetry", response_model=List[TelemetryPoint])
def get_telemetry(machine_id: int, db: Session = Depends(get_db)):
    """Recent telemetry readings for a machine."""
    rows = db.execute(text("""
        SELECT timestamp, volt, rotate, pressure, vibration
        FROM telemetry
        WHERE machine_id = :mid
        ORDER BY timestamp ASC
        LIMIT 50
    """), {"mid": machine_id}).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No telemetry found for this machine")

    return [
        TelemetryPoint(
            timestamp=str(r.timestamp),
            volt=r.volt,
            rotate=r.rotate,
            pressure=r.pressure,
            vibration=r.vibration,
        )
        for r in rows
    ]
