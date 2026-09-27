"""
consumer.py — Kafka consumer for FleetGuard vehicle telemetry.

Reads raw telemetry events from the "vehicle-telemetry" topic,
runs ML inference, and writes predictions + telemetry to PostgreSQL.

Pipeline:
  Kafka topic: vehicle-telemetry
      ↓ (JSON event per machine per tick)
  Feature engineering (rolling stats from DB)
      ↓
  predict_fast()  (sklearn RF, ~5ms)
      ↓
  PostgreSQL: telemetry + predictions + machines tables
      ↓
  FastAPI → React Dashboard (live poll)

Run:
  python streaming/consumer.py
  (or via Docker: service "consumer" in docker-compose.yml)
"""

import os
import sys
import json
import time
import logging
import signal
from datetime import datetime, timezone

# Allow importing from backend and simulator packages
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fleetguard.consumer")

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")
TOPIC             = os.getenv("KAFKA_TOPIC", "vehicle-telemetry")
GROUP_ID          = os.getenv("KAFKA_GROUP_ID", "fleetguard-consumer")

# ── DB setup ──────────────────────────────────────────────────────────────────
from app.database.connection import SessionLocal
from sqlalchemy import text


def get_db():
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        raise


# ── ML inference ──────────────────────────────────────────────────────────────
from app.services.ml_service import predict_fast


# ── Feature engineering ───────────────────────────────────────────────────────

def build_features(event: dict, db) -> dict:
    """
    Build the full feature vector expected by the ML model from:
      - current raw telemetry (event)
      - rolling stats from the last 50 rows in DB (approx 3h/24h windows)
      - machine metadata from DB
    """
    mid = event["machine_id"]

    # Machine metadata
    row = db.execute(text(
        "SELECT model, age FROM machines WHERE machine_id = :mid"
    ), {"mid": mid}).fetchone()

    model_map = {"Model A": 0, "Model B": 1, "Model C": 2, "Model D": 3}
    model_idx = float(model_map.get(row.model, 0)) if row else 0.0
    age       = float(row.age) if row else 5.0

    # Rolling stats (last 50 DB rows ≈ 3h window at 1 row/tick)
    stats = db.execute(text("""
        SELECT
            AVG(volt)      AS volt_mean,  STDDEV(volt)      AS volt_std,
            AVG(rotate)    AS rot_mean,   STDDEV(rotate)    AS rot_std,
            AVG(pressure)  AS pres_mean,  STDDEV(pressure)  AS pres_std,
            AVG(vibration) AS vib_mean,   STDDEV(vibration) AS vib_std
        FROM (
            SELECT volt, rotate, pressure, vibration
            FROM telemetry
            WHERE machine_id = :mid
            ORDER BY timestamp DESC
            LIMIT 50
        ) sub
    """), {"mid": mid}).fetchone()

    def s(v):
        return float(v) if v is not None else 0.0

    volt      = float(event["volt"])
    rotate    = float(event["rotate"])
    pressure  = float(event["pressure"])
    vibration = float(event["vibration"])

    return {
        "volt":               volt,
        "rotate":             rotate,
        "pressure":           pressure,
        "vibration":          vibration,
        "volt_mean3h":        s(stats.volt_mean)  if stats else volt,
        "volt_std3h":         s(stats.volt_std)   if stats else 0.0,
        "rotate_mean3h":      s(stats.rot_mean)   if stats else rotate,
        "rotate_std3h":       s(stats.rot_std)    if stats else 0.0,
        "pressure_mean3h":    s(stats.pres_mean)  if stats else pressure,
        "pressure_std3h":     s(stats.pres_std)   if stats else 0.0,
        "vibration_mean3h":   s(stats.vib_mean)   if stats else vibration,
        "vibration_std3h":    s(stats.vib_std)    if stats else 0.0,
        "volt_mean24h":       s(stats.volt_mean)  if stats else volt,
        "volt_std24h":        s(stats.volt_std)   if stats else 0.0,
        "rotate_mean24h":     s(stats.rot_mean)   if stats else rotate,
        "rotate_std24h":      s(stats.rot_std)    if stats else 0.0,
        "pressure_mean24h":   s(stats.pres_mean)  if stats else pressure,
        "pressure_std24h":    s(stats.pres_std)   if stats else 0.0,
        "vibration_mean24h":  s(stats.vib_mean)   if stats else vibration,
        "vibration_std24h":   s(stats.vib_std)    if stats else 0.0,
        "error_error1_count": 0.0,
        "error_error2_count": 0.0,
        "error_error3_count": 0.0,
        "error_error4_count": 0.0,
        "error_error5_count": 0.0,
        "model_idx":          model_idx,
        "age":                age,
    }


# ── DB writes ─────────────────────────────────────────────────────────────────

def process_event(event: dict, db) -> None:
    """Process one telemetry event: feature eng → ML → write to DB."""
    mid       = event["machine_id"]
    ts        = event.get("timestamp", datetime.now(timezone.utc).isoformat())
    volt      = float(event["volt"])
    rotate    = float(event["rotate"])
    pressure  = float(event["pressure"])
    vibration = float(event["vibration"])

    # 1. Insert raw telemetry
    db.execute(text("""
        INSERT INTO telemetry (machine_id, timestamp, volt, rotate, pressure, vibration)
        VALUES (:machine_id, :timestamp, :volt, :rotate, :pressure, :vibration)
    """), {
        "machine_id": mid,
        "timestamp":  ts,
        "volt":       round(volt, 4),
        "rotate":     round(rotate, 4),
        "pressure":   round(pressure, 4),
        "vibration":  round(vibration, 4),
    })

    # 2. Build features & run fast ML inference
    features = build_features(event, db)
    prob, risk_level, action = predict_fast(features)

    # 3. Update machine risk level
    db.execute(text("""
        UPDATE machines
        SET failure_probability = :prob, risk_level = :risk
        WHERE machine_id = :mid
    """), {"prob": round(prob, 4), "risk": risk_level, "mid": mid})

    # 4. Insert prediction record
    db.execute(text("""
        INSERT INTO predictions
            (machine_id, failure_probability, risk_level, recommended_action, explanation)
        VALUES (:mid, :prob, :risk, :action, :explanation)
    """), {
        "mid":         mid,
        "prob":        round(prob, 4),
        "risk":        risk_level,
        "action":      action,
        "explanation": json.dumps({}),  # SHAP computed on-demand in prediction endpoint
    })

    # 5. Auto-alert on critical machines
    existing_alert = db.execute(text("""
        SELECT 1 FROM alerts
        WHERE machine_id = :mid AND resolved = FALSE
        LIMIT 1
    """), {"mid": mid}).fetchone()

    if risk_level == "critical" and not existing_alert:
        db.execute(text("""
            INSERT INTO alerts (machine_id, risk_level, message)
            VALUES (:mid, :risk, :msg)
        """), {
            "mid":  mid,
            "risk": risk_level,
            "msg":  "Machine %d reached CRITICAL failure risk (%d%%) via Kafka stream" % (mid, round(prob*100)),
        })
    elif risk_level != "critical" and existing_alert:
        db.execute(text("""
            UPDATE alerts SET resolved = TRUE
            WHERE machine_id = :mid AND resolved = FALSE
        """), {"mid": mid})

    db.commit()


# ── Main consumer loop ────────────────────────────────────────────────────────

_running = True

def _shutdown(sig, frame):
    global _running
    logger.info("[Consumer] Shutting down...")
    _running = False

signal.signal(signal.SIGINT,  _shutdown)
signal.signal(signal.SIGTERM, _shutdown)


def run():
    logger.info(f"[Consumer] Connecting to Kafka at {BOOTSTRAP_SERVERS}, topic={TOPIC}")

    # Wait for Kafka to be ready (Docker startup delay)
    for attempt in range(30):
        try:
            from kafka import KafkaConsumer
            consumer = KafkaConsumer(
                TOPIC,
                bootstrap_servers=BOOTSTRAP_SERVERS,
                group_id=GROUP_ID,
                auto_offset_reset="latest",   # only process new messages
                enable_auto_commit=True,
                value_deserializer=lambda b: json.loads(b.decode("utf-8")),
                consumer_timeout_ms=2000,     # poll timeout
                api_version_auto_timeout_ms=10000,
            )
            logger.info("[Consumer] Connected to Kafka ✓")
            break
        except Exception as e:
            logger.warning(f"[Consumer] Kafka not ready (attempt {attempt+1}/30): {e}")
            time.sleep(3)
    else:
        logger.error("[Consumer] Could not connect to Kafka after 30 attempts. Exiting.")
        return

    db = get_db()
    msgs_processed = 0

    try:
        while _running:
            try:
                records = consumer.poll(timeout_ms=1000)
                for tp, messages in records.items():
                    for msg in messages:
                        try:
                            process_event(msg.value, db)
                            msgs_processed += 1
                            if msgs_processed % 50 == 0:
                                logger.info(
                                    f"[Consumer] Processed {msgs_processed} events | "
                                    f"last machine_id={msg.value.get('machine_id')}"
                                )
                        except Exception as e:
                            logger.error(f"[Consumer] Error processing event: {e}")
                            try:
                                db.rollback()
                            except Exception:
                                pass
            except Exception as e:
                logger.warning(f"[Consumer] Poll error: {e}")
                time.sleep(1)
    finally:
        try:
            consumer.close()
            db.close()
        except Exception:
            pass
        logger.info(f"[Consumer] Stopped. Total events processed: {msgs_processed}")


if __name__ == "__main__":
    run()
