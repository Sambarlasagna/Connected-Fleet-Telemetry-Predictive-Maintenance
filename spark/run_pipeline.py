"""
run_pipeline.py — Run the full PySpark batch pipeline end-to-end.

Steps:
  1. Export DB tables to CSV (no JDBC jar needed)
  2. Preprocessing  → data/processed/telemetry_clean.parquet
  3. Feature Eng    → data/processed/telemetry_features.parquet
  4. Batch Inference→ data/processed/batch_predictions.parquet
                   → data/reports/fleet_risk_report.csv

Usage:
    python spark/run_pipeline.py
"""

import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)


def export_db_to_csv():
    """Export telemetry + machines tables from Postgres to CSV for Spark."""
    print("[Export] Exporting DB tables to CSV...")
    import pandas as pd
    from sqlalchemy import create_engine, text

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://fleetguard:fleetguard@localhost:5433/fleetguard"
    )
    engine = create_engine(db_url)

    os.makedirs(os.path.join(ROOT, "data", "raw"), exist_ok=True)

    with engine.connect() as conn:
        tel = pd.read_sql("SELECT * FROM telemetry ORDER BY machine_id, timestamp", conn)
        mac = pd.read_sql("SELECT * FROM machines", conn)

    tel_path = os.path.join(ROOT, "data", "raw", "telemetry.csv")
    mac_path = os.path.join(ROOT, "data", "raw", "machines.csv")

    tel.to_csv(tel_path, index=False)
    mac.to_csv(mac_path, index=False)

    print(f"       Exported {len(tel):,} telemetry rows to {tel_path}")
    print(f"       Exported {len(mac):,} machines to {mac_path}")
    return len(tel)


def run_step(name: str, script: str):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        env={**os.environ},
    )
    if result.returncode != 0:
        print(f"[ERROR] {name} failed with code {result.returncode}")
        sys.exit(result.returncode)
    print(f"[OK] {name} completed")


def main():
    print("\n" + "="*60)
    print("  FleetGuard — PySpark Batch Pipeline")
    print("="*60)

    # Step 0: Export DB to CSV (Spark fallback — no JDBC jar needed)
    row_count = export_db_to_csv()
    if row_count < 10:
        print("[WARNING] Very few telemetry rows in DB. Run the simulation first!")

    # Step 1: Preprocessing
    run_step(
        "Step 1/3: Preprocessing (clean + validate)",
        os.path.join(ROOT, "spark", "preprocessing", "preprocessing.py")
    )

    # Step 2: Feature Engineering
    run_step(
        "Step 2/3: Feature Engineering (rolling windows)",
        os.path.join(ROOT, "spark", "feature_engineering", "feature_engineering.py")
    )

    # Step 3: Batch Inference
    run_step(
        "Step 3/3: Batch Inference (sklearn RF via Pandas UDF)",
        os.path.join(ROOT, "spark", "batch_inference", "batch_inference.py")
    )

    report_path = os.path.join(ROOT, "data", "reports", "fleet_risk_report.csv")
    print(f"\n{'='*60}")
    print("  ✅ Pipeline complete!")
    print(f"  Fleet risk report: {report_path}")
    print("="*60)


if __name__ == "__main__":
    main()
