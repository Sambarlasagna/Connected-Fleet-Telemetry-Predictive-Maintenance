"""
simulation.py — FastAPI routes for simulation control.

POST /api/simulation/start   — start a new simulation session
POST /api/simulation/stop    — stop the running session
GET  /api/simulation/status  — current simulation status
POST /api/simulation/reset   — restore DB to original seeded snapshot
"""

import random
import sys
import os

# Ensure the project root (parent of backend/) is on sys.path so
# `simulator` package can be imported when running from backend/ directory.
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database.connection import get_db
from app.models.schemas import (
    SimulationStartRequest,
    SimulationStatusResponse,
    SimulationResetResponse,
)
from simulator.runner import runner

router = APIRouter()

# Fixed set of 10 machine IDs activated by the simulator
ACTIVE_MACHINE_IDS = list(range(1, 11))   # machines 1..10


@router.post("/simulation/start", response_model=SimulationStatusResponse)
def start_simulation(req: SimulationStartRequest, db: Session = Depends(get_db)):
    """
    Start a new simulation session.

    - `scenario`: fault scenario to apply to all active machines
      (normal | overheat | voltage_spike | bearing_wear | degradation | random_fault)
    - `speed`: 1.0 (real-time), 2.0 (2x), or 5.0 (5x)
    - `demo`: if True, ignore `scenario` and run the scripted interview demo
    """
    if runner.is_running:
        raise HTTPException(status_code=409, detail="Simulation already running. Stop it first.")

    valid_scenarios = {"normal", "overheat", "voltage_spike", "bearing_wear", "degradation", "random_fault"}
    if req.scenario not in valid_scenarios:
        raise HTTPException(status_code=422, detail=f"Unknown scenario '{req.scenario}'. Valid: {sorted(valid_scenarios)}")

    valid_speeds = {1.0, 2.0, 5.0}
    if req.speed not in valid_speeds:
        raise HTTPException(status_code=422, detail=f"Speed must be one of {sorted(valid_speeds)}")

    # Fetch machine metadata (model_idx, age) from DB for VehicleState init
    rows = db.execute(text("""
        SELECT machine_id, model, age FROM machines
        WHERE machine_id = ANY(:ids)
    """), {"ids": ACTIVE_MACHINE_IDS}).fetchall()

    model_map = {"Model A": 0, "Model B": 1, "Model C": 2, "Model D": 3}
    machine_meta = {
        r.machine_id: {
            "model_idx": model_map.get(r.model, 0),
            "age":       r.age,
        }
        for r in rows
    }

    runner.start(
        get_db=get_db,
        machine_ids=ACTIVE_MACHINE_IDS,
        scenario=req.scenario,
        speed=req.speed,
        demo=req.demo,
        machine_meta=machine_meta,
    )

    return SimulationStatusResponse(**runner.get_status())


@router.post("/simulation/stop", response_model=SimulationStatusResponse)
def stop_simulation():
    """Stop the running simulation."""
    if not runner.is_running:
        raise HTTPException(status_code=409, detail="No simulation is currently running.")
    runner.stop()
    return SimulationStatusResponse(**runner.get_status())


@router.get("/simulation/status", response_model=SimulationStatusResponse)
def get_simulation_status():
    """Return the current simulation status (running, ticks, degradations, etc.)."""
    return SimulationStatusResponse(**runner.get_status())


@router.post("/simulation/reset", response_model=SimulationResetResponse)
def reset_simulation(db: Session = Depends(get_db)):
    """
    Stop simulation (if running) and restore the database to the original
    seeded snapshot — wipes simulation telemetry, restores risk levels.
    """
    try:
        runner.reset_db(db)
        return SimulationResetResponse(success=True, message="Database restored to original seed snapshot.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset failed: {e}")
