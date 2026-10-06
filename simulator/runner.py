"""
runner.py - Simulation orchestrator for FleetGuard.

Manages a pool of VehicleState machines, ticks them on a background thread,
writes telemetry + predictions + updated machine risk levels to PostgreSQL.
"""

import threading
import time
import json
import traceback
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from simulator.vehicle import VehicleState
from simulator.scenarios import SCENARIOS, DEMO_SCRIPT
from app.services.ml_service import predict_fast

# Simulator always writes directly to DB (includes ML inference + risk updates).
# Kafka streaming is a separate pipeline for external telemetry ingestion.
# We intentionally bypass Kafka here so predictions always reach the DB.
_KAFKA_AVAILABLE = False
def send_telemetry(event): return False
def kafka_flush(): pass


# -- Singleton runner ----------------------------------------------------------

class SimulationRunner:

    def __init__(self):
        self._lock      = threading.Lock()
        self._thread    = None
        self._stop_evt  = threading.Event()
        self.is_running   = False
        self.is_demo      = False
        self.speed        = 1.0
        self.scenario     = "normal"
        self.tick_count   = 0
        self.started_at   = None
        self.active_machine_ids = []
        self.kafka_mode   = False
        self._vehicles    = {}
        self._get_db      = None

    # -- Public API ------------------------------------------------------------

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

            self._vehicles = {}
            for mid in machine_ids:
                meta = machine_meta.get(mid, {})
                s = scenario if not demo else "normal"
                self._vehicles[mid] = VehicleState(
                    machine_id=mid,
                    model_idx=meta.get("model_idx", 0),
                    age=meta.get("age", 5),
                    scenario=s,
                    degradation_rate=0.008 * speed,
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
        with self._lock:
            return {
                "is_running":           self.is_running,
                "is_demo":              self.is_demo,
                "scenario":             self.scenario,
                "speed":                self.speed,
                "tick_count":           self.tick_count,
                "active_machines":      list(self.active_machine_ids),
                "started_at":           self.started_at.isoformat() if self.started_at else None,
                "vehicle_degradations": {
                    mid: round(v.degradation, 3)
                    for mid, v in self._vehicles.items()
                },
                "kafka_mode":           self.kafka_mode,
            }

    def reset_db(self, db: Session) -> None:
        """Wipe simulation-added telemetry and restore machine risk levels."""
        self.stop()
        time.sleep(0.5)

        db.execute(text("""
            DELETE FROM telemetry
            WHERE id NOT IN (
                SELECT MIN(id) FROM telemetry GROUP BY machine_id
            )
        """))

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

    # -- Background loop -------------------------------------------------------

    def _run_loop(self):
        interval = 1.0 / self.speed
        print("[SimRunner] Loop started: speed=" + str(self.speed) + "x demo=" + str(self.is_demo)
              + " machines=" + str(list(self._vehicles.keys())))

        while not self._stop_evt.is_set():
            tick_start = time.monotonic()
            self.tick_count += 1
            db_gen = None
            db = None

            try:
                # Apply demo script scenarios at the right ticks
                if self.is_demo:
                    for mid, start_tick, sc in DEMO_SCRIPT:
                        if self.tick_count == start_tick and mid in self._vehicles:
                            self._vehicles[mid].set_scenario(sc)
                            print("[SimRunner] Demo tick " + str(self.tick_count)
                                  + ": machine " + str(mid) + " -> " + sc)

                # Get a DB session
                db_gen = self._get_db()
                db = next(db_gen)

                for mid, vehicle in self._vehicles.items():
                    try:
                        vehicle.tick()
                        row = vehicle.telemetry_row()

                        # Try Kafka first; fall back to direct DB
                        kafka_sent = False
                        if _KAFKA_AVAILABLE:
                            event = {
                                **row,
                                "timestamp":   str(row["timestamp"]),
                                "scenario":    vehicle.scenario,
                                "degradation": round(vehicle.degradation, 4),
                            }
                            kafka_sent = send_telemetry(event)

                        if kafka_sent:
                            self.kafka_mode = True
                            continue

                        # Direct-DB fallback
                        self.kafka_mode = False
                        db.execute(text(
                            "INSERT INTO telemetry "
                            "(machine_id, timestamp, volt, rotate, pressure, vibration) "
                            "VALUES (:machine_id, :timestamp, :volt, :rotate, :pressure, :vibration)"
                        ), row)

                        feats = vehicle.feature_vector()
                        prob, risk_level, action = predict_fast(feats)

                        db.execute(text(
                            "UPDATE machines "
                            "SET failure_probability = :prob, risk_level = :risk, updated_at = NOW() "
                            "WHERE machine_id = :mid"
                        ), {"prob": round(prob, 4), "risk": risk_level, "mid": mid})

                        db.execute(text(
                            "INSERT INTO predictions "
                            "(machine_id, failure_probability, risk_level, recommended_action, explanation) "
                            "VALUES (:mid, :prob, :risk, :action, :explanation)"
                        ), {
                            "mid":         mid,
                            "prob":        round(prob, 4),
                            "risk":        risk_level,
                            "action":      action,
                            "explanation": json.dumps({}),
                        })

                        if risk_level == "critical":
                            existing = db.execute(text(
                                "SELECT 1 FROM alerts "
                                "WHERE machine_id = :mid AND resolved = FALSE LIMIT 1"
                            ), {"mid": mid}).fetchone()
                            if not existing:
                                db.execute(text(
                                    "INSERT INTO alerts (machine_id, risk_level, message) "
                                    "VALUES (:mid, 'critical', :msg)"
                                ), {
                                    "mid": mid,
                                    "msg": "Machine " + str(mid).zfill(3) + ": critical failure risk detected.",
                                })

                    except Exception as vehicle_err:
                        print("[SimRunner] tick=" + str(self.tick_count)
                              + " machine=" + str(mid) + " error: " + str(vehicle_err))
                        try:
                            db.rollback()
                        except Exception:
                            pass

                db.commit()
                kafka_flush()

            except Exception as tick_err:
                print("[SimRunner] TICK " + str(self.tick_count) + " FATAL: " + str(tick_err))
                traceback.print_exc()
                if db is not None:
                    try:
                        db.rollback()
                    except Exception:
                        pass

            finally:
                # Always return the DB connection to the pool
                if db_gen is not None:
                    try:
                        next(db_gen)
                    except StopIteration:
                        pass
                    except Exception:
                        pass

            # Sleep for remainder of interval
            elapsed = time.monotonic() - tick_start
            self._stop_evt.wait(timeout=max(0.0, interval - elapsed))

        self.is_running = False


# -- Module-level singleton ----------------------------------------------------
runner = SimulationRunner()
