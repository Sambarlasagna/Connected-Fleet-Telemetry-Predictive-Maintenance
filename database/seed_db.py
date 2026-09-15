"""
seed_db.py — Load JSON seed data into PostgreSQL.

Run after the database is up:
    python database/seed_db.py
"""

import os
import json
import psycopg2
from psycopg2.extras import Json

DB_URL = os.getenv("DATABASE_URL", "postgresql://fleetguard:fleetguard@localhost:5433/fleetguard")
SEED_DIR = os.path.join(os.path.dirname(__file__), "seed")


def connect():
    import re
    m = re.match(r"postgresql://(\w+):(\w+)@([\w.]+):(\d+)/(\w+)", DB_URL)
    if not m:
        raise ValueError(f"Cannot parse DATABASE_URL: {DB_URL}")
    user, password, host, port, dbname = m.groups()
    return psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)


def seed():
    conn = connect()
    cur = conn.cursor()

    # Load seed files
    with open(os.path.join(SEED_DIR, "machines.json")) as f:
        machines = json.load(f)

    with open(os.path.join(SEED_DIR, "predictions.json")) as f:
        predictions = json.load(f)

    with open(os.path.join(SEED_DIR, "telemetry_latest.json")) as f:
        telemetry = json.load(f)

    # ── Machines ──────────────────────────────────────────────────────────────
    print(f"Seeding {len(machines)} machines...")
    for m in machines:
        cur.execute("""
            INSERT INTO machines (machine_id, machine_name, model, age, risk_level, failure_probability)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (machine_id) DO UPDATE SET
                risk_level = EXCLUDED.risk_level,
                failure_probability = EXCLUDED.failure_probability,
                updated_at = NOW()
        """, (m["machine_id"], m["machine_name"], m["model"], m["age"],
              m["risk_level"], m["failure_probability"]))

    # ── Telemetry ─────────────────────────────────────────────────────────────
    print(f"Seeding {len(telemetry)} telemetry rows...")
    for t in telemetry:
        cur.execute("""
            INSERT INTO telemetry (machine_id, timestamp, volt, rotate, pressure, vibration)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (t["machine_id"], t["timestamp"], t["volt"], t["rotate"],
              t["pressure"], t["vibration"]))

    # ── Predictions ───────────────────────────────────────────────────────────
    print(f"Seeding {len(predictions)} predictions...")
    for p in predictions:
        cur.execute("""
            INSERT INTO predictions (machine_id, failure_probability, risk_level, recommended_action, explanation)
            VALUES (%s, %s, %s, %s, %s)
        """, (p["machine_id"], p["failure_probability"], p["risk_level"],
              p["recommended_action"], Json(p["explanation"])))

    # ── Alerts for critical machines ──────────────────────────────────────────
    alert_msgs = {
        "critical": "High failure risk detected. Immediate inspection required.",
        "at_risk":  "Sensor readings indicate elevated risk. Schedule maintenance.",
    }
    critical_machines = [m for m in machines if m["risk_level"] in ("critical", "at_risk")]
    print(f"Seeding {len(critical_machines)} alerts...")
    for m in critical_machines:
        cur.execute("""
            INSERT INTO alerts (machine_id, risk_level, message)
            VALUES (%s, %s, %s)
        """, (m["machine_id"], m["risk_level"], alert_msgs[m["risk_level"]]))

    conn.commit()
    cur.close()
    conn.close()
    print("[OK] Database seeded successfully!")


if __name__ == "__main__":
    seed()
