"""
run_pipeline.py — Standalone retraining pipeline runner.

Executes every step of the Airflow DAG locally without needing Airflow installed.
Useful for:
  - Local development / testing
  - Manual one-off retrains
  - CI pipeline validation

Usage:
    python airflow/run_pipeline.py
    python airflow/run_pipeline.py --min-rows 100   # lower threshold for testing
    python airflow/run_pipeline.py --dry-run        # just check data freshness
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Setup ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fleetguard.pipeline")

ROOT     = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DB_URL   = os.environ.get("DATABASE_URL",
           "postgresql://fleetguard:fleetguard@localhost:5433/fleetguard")
MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI",
             f"sqlite:///{ROOT}/mlruns/mlflow.db")

sys.path.insert(0, str(ROOT))


def step(name: str):
    """Context manager that times a step and prints a header."""
    class _Step:
        def __enter__(self):
            log.info("")
            log.info(f"{'='*55}")
            log.info(f"  STEP: {name}")
            log.info(f"{'='*55}")
            self.start = time.perf_counter()
        def __exit__(self, *_):
            elapsed = time.perf_counter() - self.start
            log.info(f"  Done in {elapsed:.1f}s")
    return _Step()


# ── Steps (mirror the DAG tasks) ──────────────────────────────────────────────

def check_freshness(min_rows: int) -> dict:
    with step("Data Freshness Check"):
        from sqlalchemy import create_engine, text
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM telemetry")).scalar()
            week  = conn.execute(text(
                "SELECT COUNT(*) FROM telemetry WHERE timestamp >= NOW() - INTERVAL '7 days'"
            )).scalar()
        log.info(f"Total rows:       {total:,}")
        log.info(f"Rows (last 7d):   {week:,}")
        log.info(f"Threshold:        {min_rows}")
        if week < min_rows:
            log.warning(f"Only {week} new rows — below threshold {min_rows}.")
            return {"total": total, "week": week, "sufficient": False}
        log.info(f"Freshness check PASSED")
        return {"total": total, "week": week, "sufficient": True}


def export_telemetry() -> Path:
    with step("Export Telemetry → CSV"):
        import pandas as pd
        from sqlalchemy import create_engine
        engine = create_engine(DB_URL)
        raw_dir = DATA_DIR / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        with engine.connect() as conn:
            tel = pd.read_sql("SELECT * FROM telemetry ORDER BY machine_id, timestamp", conn)
            mac = pd.read_sql("SELECT * FROM machines", conn)

        tel_path = raw_dir / "telemetry.csv"
        mac_path  = raw_dir / "machines.csv"
        tel.to_csv(tel_path, index=False)
        mac.to_csv(mac_path,  index=False)

        log.info(f"Exported {len(tel):,} telemetry rows → {tel_path}")
        log.info(f"Exported {len(mac)} machines → {mac_path}")
        return tel_path


def run_spark(script_path: Path, name: str):
    with step(name):
        if not script_path.exists():
            log.warning(f"Script not found: {script_path} — skipping")
            return
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            log.error(result.stderr[-3000:])
            raise RuntimeError(f"{name} failed (exit code {result.returncode})")
        log.info(result.stdout[-1500:])


def run_training_sweep() -> list[dict]:
    with step("MLflow Training Sweep (5 configs)"):
        from ml.training.train_with_mlflow import train

        configs = [
            (100,  8,  10),
            (50,   6,  10),
            (100,  10,  5),
            (200,  8,  10),
            (200,  12,  5),
        ]

        results = []
        for n, d, l in configs:
            log.info(f"  Training n={n} d={d} leaf={l} ...")
            metrics, run_id = train(
                n_estimators=n,
                max_depth=d,
                min_samples_leaf=l,
            )
            results.append({
                "run_id":   run_id,
                "auc_roc":  metrics.get("auc_roc", 0),
                "f1":       metrics.get("f1", 0),
                "n_estimators": n,
                "max_depth": d,
            })
            log.info(f"    AUC={metrics.get('auc_roc', 0):.4f}  F1={metrics.get('f1', 0):.4f}")

        best = max(results, key=lambda r: r["auc_roc"])
        log.info(f"  Best: run={best['run_id'][:16]}  AUC={best['auc_roc']:.4f}")
        return results


def promote_best(results: list[dict]) -> str:
    with step("Promote Best Model → Production"):
        import mlflow
        from mlflow import MlflowClient

        MODEL_NAME = "fleetguard-rf"
        mlflow.set_tracking_uri(MLFLOW_URI)
        client = MlflowClient(tracking_uri=MLFLOW_URI)

        best = max(results, key=lambda r: r["auc_roc"])
        best_run_id = best["run_id"]

        # Find the model version for this run
        versions = client.search_model_versions(f"name='{MODEL_NAME}'")
        promoted = None
        for v in versions:
            if v.run_id == best_run_id:
                client.transition_model_version_stage(
                    name=MODEL_NAME,
                    version=v.version,
                    stage="Production",
                    archive_existing_versions=True,
                )
                promoted = v.version
                log.info(f"Promoted model v{v.version} → Production")
                log.info(f"Run ID: {best_run_id}")
                log.info(f"AUC-ROC: {best['auc_roc']:.4f}")
                break

        if promoted is None:
            log.warning("Could not find model version to promote.")
        return promoted


def save_summary(data_stats: dict, results: list[dict], promoted_version):
    with step("Save Summary Report"):
        report_dir = DATA_DIR / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        run_date = datetime.now().strftime("%Y-%m-%d")
        best = max(results, key=lambda r: r["auc_roc"])
        summary = {
            "run_date":        datetime.now().isoformat(),
            "total_telemetry": data_stats["total"],
            "new_rows_7d":     data_stats["week"],
            "configs_trained": len(results),
            "best_run_id":     best["run_id"],
            "best_auc_roc":    best["auc_roc"],
            "best_f1":         best["f1"],
            "promoted_version": promoted_version,
            "all_runs": results,
        }
        path = report_dir / f"retrain_summary_{run_date}.json"
        with open(path, "w") as f:
            json.dump(summary, f, indent=2)
        log.info(f"Summary saved → {path}")
        return summary


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="FleetGuard retraining pipeline")
    parser.add_argument("--min-rows", type=int, default=100,
                        help="Minimum new telemetry rows required (default: 100)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only check data freshness, don't train")
    parser.add_argument("--skip-spark", action="store_true",
                        help="Skip PySpark steps (useful without Java)")
    args = parser.parse_args()

    start = time.perf_counter()
    log.info("")
    log.info("FleetGuard — Automated Retraining Pipeline")
    log.info(f"Started: {datetime.now().isoformat()}")
    log.info(f"DB:      {DB_URL}")
    log.info(f"MLflow:  {MLFLOW_URI}")

    # Step 1 — freshness check
    stats = check_freshness(args.min_rows)
    if not stats["sufficient"]:
        log.warning("Aborting — not enough new data.")
        sys.exit(0)

    if args.dry_run:
        log.info("--dry-run: stopping after freshness check.")
        sys.exit(0)

    # Step 2 — export
    export_telemetry()

    # Steps 3 + 4 — PySpark
    if not args.skip_spark:
        run_spark(ROOT / "spark" / "preprocessing" / "preprocessing.py",
                  "PySpark Preprocessing")
        run_spark(ROOT / "spark" / "feature_engineering" / "feature_engineering.py",
                  "PySpark Feature Engineering")
    else:
        log.info("Skipping PySpark steps (--skip-spark)")

    # Steps 5 + 6 — training sweep
    results = run_training_sweep()

    # Step 7 — promote
    promoted = promote_best(results)

    # Step 8 — summary
    summary = save_summary(stats, results, promoted)

    elapsed = time.perf_counter() - start
    log.info("")
    log.info("=" * 55)
    log.info("  PIPELINE COMPLETE")
    log.info("=" * 55)
    log.info(f"  Total time:    {elapsed/60:.1f} minutes")
    log.info(f"  Configs tried: {len(results)}")
    log.info(f"  Best AUC-ROC:  {summary['best_auc_roc']:.4f}")
    log.info(f"  Model version: v{promoted} (Production)")
    log.info("=" * 55)


if __name__ == "__main__":
    main()
