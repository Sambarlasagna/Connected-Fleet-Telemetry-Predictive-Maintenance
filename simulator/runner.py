"""
runner.py — Simulation orchestrator for FleetGuard.

Manages a pool of VehicleState machines, ticks them on a background thread,
writes telemetry + predictions + updated machine risk levels to PostgreSQL.

Usage (from FastAPI routes):
    runner.start(config)
    runner.stop()
    runner.get_status()
    runner.reset_db(db)
"""

import threading
import time
import random
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from simulator.vehicle import VehicleState
from simulator.scenarios import SCENARIOS, DEMO_SCRIPT
from app.services.ml_service import predict_fast


# ── Singleton session ──────────────────────────────────────────────────────────

class SimulationRunner:

    def __init__(self):
        self._lock      = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_evt  = threading.Event()

        # State
        self.is_running   = False
        self.is_demo      = False
        self.speed        = 1.0
        self.scenario     = "normal"
        self.tick_count   = 0
        self.started_at:  Optional[datetime] = None
        self.active_machine_ids: List[int] = []

        # Active vehicle states
        self._vehicles: Dict[int, VehicleState] = {}

        # DB session factory (set by start())
        self._get_db = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self, get_db, machine_ids: List[int], scenario: str,
              speed: float, demo: bool, machine_meta: Dict[int, Dict]) -> None:
        """Start the simulation background thread."""
        with self._lock:
            if self.is_running:
                return

            self._get_db = get_db
            self._stop_evt.clear()
            self.is_running   = True
            self.is_demo      = demo
            self.speed        = speed
            self.scenario     = scenario
            self.tick_count   = 0
            self.started_at   = datetime.now(timezone.utc)
            self.active_machine_ids = machine_ids

            # Build vehicle state machines
            self._vehicles = {}
            for mid in machine_ids:
                meta = machine_meta.get(mid, {})
                s = scenario if not demo else "normal"
                self._vehicles[mid] = VehicleState(
                    machine_id=mid,
                    model_idx=meta.get("model_idx", 0),
                    age=meta.get("age", 5),
                    scenario=s,
                    degradation_rate=0.008 * speed,  # faster speed = faster degradation
                )

            self._thread = threading.Thread(
                target=self._run_loop, daemon=True, name="SimRunner"
            )
            self._thread.start()

    def stop(self) -> None:
        """Signal the background thread to stop."""
        self._stop_evt.set()
        self.is_running = False

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running":    self.is_running,
            "is_demo":       self.is_demo,
            "scenario":      self.scenario,
            "speed":         self.speed,
            "tick_count":    self.tick_count,
            "active_machines": self.active_machine_ids,
            "started_at":    self.started_at.isoformat() if self.started_at else None,
            "vehicle_degradations": {
                mid: round(v.degradation, 3)
                for mid, v in self._vehicles.items()
            },
        }

    def reset_db(self, db: Session) -> None:
        """
        Wipe simulation-added telemetry and restore machine risk levels
        to the original seeded snapshot stored in the predictions table.
        """
        self.stop()
        time.sleep(0.5)  # Let the loop drain

        # Keep only the first (seeded) telemetry row per machine
        db.execute(text("""
            DELETE FROM telemetry
            WHERE id NOT IN (
                SELECT MIN(id) FROM telemetry GROUP BY machine_id
            )
        """))

        # Restore machine risk from the original predictions row
        db.execute(text("""
            UPDATE machines m
            SET risk_level          = p.risk_level,
                failure_probability = p.failure_probability,
                updated_at          = NOW()
            FROM (
                SELECT DISTINCT ON (machine_id)
                    machine_id, risk_level, failure_probability
                FROM predictions
                ORDER BY machine_id, id ASC
            ) p
            WHERE m.machine_id = p.machine_id
        """))

        # Delete any simulation-added prediction rows (keep first per machine)
        db.execute(text("""
            DELETE FROM predictions
            WHERE id NOT IN (
                SELECT MIN(id) FROM predictions GROUP BY machine_id
            )
        """))

        db.commit()
        self.tick_count = 0
        self.active_machine_ids = []
        self._vehicles = {}

    # ── Background loop ────────────────────────────────────────────────────────

    def _run_loop(self):
        interval = 1.0 / self.speed

        while not self._stop_evt.is_set():
            tick_start = time.monotonic()
            self.tick_count += 1

            try:
                # Apply demo script scenarios at the right ticks
                if self.is_demo:
                    for mid, start_tick, sc in DEMO_SCRIPT:
                        if (self.tick_count == start_tick and
                                mid in self._vehicles):
                            self._vehicles[mid].set_scenario(sc)

                db_gen = self._get_db()
                db: Session = next(db_gen)

                for mid, vehicle in self._vehicles.items():
                    try:
                        # Tick the vehicle
                        vehicle.tick()

                        # Build and insert telemetry row
                        row = vehicle.telemetry_row()
                        db.execute(text("""
                            INSERT INTO telemetry (machine_id, timestamp, volt, rotate, pressure, vibration)
                            VALUES (:machine_id, :timestamp, :volt, :rotate, :pressure, :vibration)
                        """), row)

                        # Run fast ML inference (no SHAP — keeps simulation real-time)
                        feats = vehicle.feature_vector()
                        prob, risk_level, action = predict_fast(feats)

                        # Update machine record
                        db.execute(text("""
                            UPDATE machines
                            SET failure_probability = :prob,
                                risk_level          = :risk,
                                updated_at          = NOW()
                            WHERE machine_id = :mid
                        """), {"prob": round(prob, 4), "risk": risk_level, "mid": mid})

                        # Insert prediction row (no SHAP in sim — fast path)
                        db.execute(text("""
                            INSERT INTO predictions (machine_id, failure_probability, risk_level, recommended_action, explanation)
                            VALUES (:mid, :prob, :risk, :action, :explanation)
                        """), {
                            "mid":         mid,
                            "prob":        round(prob, 4),
                            "risk":        risk_level,
                            "action":      action,
                            "explanation": json.dumps({}),
                        })

                        # Auto-generate alert when machine transitions to critical
                        if risk_level == "critical":
                            existing = db.execute(text("""
                                SELECT 1 FROM alerts
                                WHERE machine_id = :mid AND resolved = FALSE
                                LIMIT 1
                            """), {"mid": mid}).fetchone()
                            if not existing:
                                db.execute(text("""
                                    INSERT INTO alerts (machine_id, risk_level, message)
                                    VALUES (:mid, 'critical', :msg)
                                """), {
                                    "mid": mid,
                                    "msg": f"Machine {mid:03d}: critical failure risk detected by ML model.",
                                })

                    except Exception as e:
                        print(f"[SimRunner] Error on machine {mid}: {e}")

                db.commit()
                try:
                    next(db_gen)
                except StopIteration:
                    pass

            except Exception as e:
                print(f"[SimRunner] DB error: {e}")

            # Sleep for remainder of interval
            elapsed = time.monotonic() - tick_start
            sleep_time = max(0.0, interval - elapsed)
            self._stop_evt.wait(timeout=sleep_time)

        self.is_running = False


# ── Module-level singleton ─────────────────────────────────────────────────────
runner = SimulationRunner()
