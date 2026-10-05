"""
fleetguard_retrain_dag.py — Airflow DAG: automated model retraining pipeline.

Schedule: Every Sunday at 2am (weekly retrain on fresh telemetry).
Can also be triggered manually from the Airflow UI.

Pipeline:
  1. data_freshness_check   — verify enough new telemetry rows exist
  2. export_telemetry       — dump PostgreSQL → CSV (Spark input)
  3. spark_preprocessing    — clean + validate raw telemetry (PySpark)
  4. spark_feature_eng      — rolling window feature engineering (PySpark)
  5. train_baseline         — train RF with default params, log to MLflow
  6. hyperparameter_sweep   — train 4 more configs, pick best AUC
  7. promote_best_model     — transition best model version to Production
  8. notify_complete        — log summary + update model_meta.json

Each task is a PythonOperator so the full logic is inspectable in this file.
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.utils.dates import days_ago

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(os.environ.get("FLEETGUARD_ROOT", "/opt/fleetguard"))
sys.path.insert(0, str(ROOT))

DB_URL    = os.environ.get("DATABASE_URL",
            "postgresql://fleetguard:fleetguard@postgres:5432/fleetguard")
MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI",
             f"sqlite:///{ROOT}/mlruns/mlflow.db")
MODEL_DIR  = ROOT / "ml" / "model"
DATA_DIR   = ROOT / "data"

MIN_NEW_ROWS = int(os.environ.get("RETRAIN_MIN_ROWS", "500"))

log = logging.getLogger("fleetguard.dag")

# ── DAG definition ─────────────────────────────────────────────────────────────

default_args = {
    "owner": "fleetguard",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    dag_id="fleetguard_model_retrain",
    description="Weekly automated model retraining pipeline for FleetGuard",
    schedule_interval="0 2 * * 0",  # Every Sunday at 2:00 AM
    start_date=days_ago(1),
    catchup=False,
    default_args=default_args,
    tags=["fleetguard", "ml", "retraining"],
    doc_md="""
# FleetGuard Model Retraining DAG

Runs every Sunday at 2:00 AM UTC.

## Pipeline steps
1. **data_freshness_check** — Short-circuits if < 500 new telemetry rows
2. **export_telemetry** — Exports DB telemetry to `data/raw/*.csv`
3. **spark_preprocessing** — PySpark cleaning + DQ scoring
4. **spark_feature_engineering** — Rolling window features (3h + 24h)
5. **train_baseline** — Trains default RF, logs to MLflow
6. **hyperparameter_sweep** — Trains 4 more configs, logs each run
7. **promote_best_model** — Sets highest AUC model to Production stage
8. **notify_complete** — Writes summary JSON + logs metrics

## Configuration
- `RETRAIN_MIN_ROWS` env var: minimum new rows required (default: 500)
- `DATABASE_URL`: PostgreSQL connection string
- `MLFLOW_TRACKING_URI`: MLflow backend store URI
    """,
)

# ── Task 1: Data freshness gate ────────────────────────────────────────────────

def check_data_freshness(**context) -> bool:
    """
    Short-circuit the DAG if not enough telemetry exists since last retrain.
    Returns True to proceed, False to skip the rest of the DAG.
    """
    import pandas as pd
    from sqlalchemy import create_engine, text

    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM telemetry"))
        total_rows = result.scalar()

        # Check rows added in the last 7 days
        result_week = conn.execute(text("""
            SELECT COUNT(*) FROM telemetry
            WHERE timestamp >= NOW() - INTERVAL '7 days'
        """))
        new_rows = result_week.scalar()

    log.info(f"Total telemetry rows: {total_rows:,}")
    log.info(f"New rows (last 7 days): {new_rows:,}")
    log.info(f"Threshold: {MIN_NEW_ROWS}")

    # Push stats to XCom for downstream tasks
    context["ti"].xcom_push(key="total_rows", value=int(total_rows))
    context["ti"].xcom_push(key="new_rows",   value=int(new_rows))

    if new_rows < MIN_NEW_ROWS:
        log.warning(
            f"Only {new_rows} new rows — below threshold {MIN_NEW_ROWS}. "
            "Skipping retraining."
        )
        return False

    log.info(f"Data freshness check PASSED: {new_rows} new rows.")
    return True


# ── Task 2: Export DB → CSV ────────────────────────────────────────────────────

def export_telemetry_to_csv(**context):
    """Export telemetry + machines from PostgreSQL to CSV for PySpark."""
    import pandas as pd
    from sqlalchemy import create_engine

    engine = create_engine(DB_URL)
    raw_dir = DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    with engine.connect() as conn:
        tel = pd.read_sql(
            "SELECT * FROM telemetry ORDER BY machine_id, timestamp", conn
        )
        mac = pd.read_sql("SELECT * FROM machines", conn)
        pred_count = pd.read_sql(
            "SELECT COUNT(*) as cnt FROM predictions", conn
        ).iloc[0]["cnt"]

    tel_path = raw_dir / "telemetry.csv"
    mac_path  = raw_dir / "machines.csv"
    tel.to_csv(tel_path, index=False)
    mac.to_csv(mac_path,  index=False)

    log.info(f"Exported {len(tel):,} telemetry rows → {tel_path}")
    log.info(f"Exported {len(mac)} machines → {mac_path}")
    log.info(f"Total predictions in DB: {pred_count:,}")

    context["ti"].xcom_push(key="telemetry_rows", value=len(tel))


# ── Task 3: PySpark preprocessing ─────────────────────────────────────────────

def run_spark_preprocessing(**context):
    """Run the PySpark preprocessing job."""
    script = ROOT / "spark" / "preprocessing" / "preprocessing.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        log.error(f"PySpark preprocessing failed:\n{result.stderr}")
        raise RuntimeError(f"PySpark preprocessing failed (code {result.returncode})")
    log.info(result.stdout[-2000:])  # last 2000 chars of stdout


# ── Task 4: PySpark feature engineering ───────────────────────────────────────

def run_spark_feature_engineering(**context):
    """Run the PySpark feature engineering job."""
    script = ROOT / "spark" / "feature_engineering" / "feature_engineering.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        log.error(f"PySpark feature engineering failed:\n{result.stderr}")
        raise RuntimeError(f"Feature engineering failed (code {result.returncode})")
    log.info(result.stdout[-2000:])


# ── Task 5 + 6: Train with MLflow ─────────────────────────────────────────────

PARAM_CONFIGS = [
    # (n_estimators, max_depth, min_samples_leaf)  — baseline first
    (100,  8,  10),
    (50,   6,  10),
    (100,  10,  5),
    (200,  8,  10),
    (200,  12,  5),
]


def train_single_run(n_estimators, max_depth, min_samples_leaf, **context):
    """Train one RF configuration and log to MLflow."""
    # Import here so Airflow worker picks up fresh modules
    sys.path.insert(0, str(ROOT))
    from ml.training.train_with_mlflow import train

    metrics, run_id = train(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
    )

    log.info(
        f"Run {run_id[:8]} | n={n_estimators} d={max_depth} | "
        f"AUC={metrics['auc_roc']:.4f} F1={metrics['f1']:.4f}"
    )
    return run_id


def train_baseline(**context):
    n, d, l = PARAM_CONFIGS[0]
    run_id = train_single_run(n, d, l, **context)
    context["ti"].xcom_push(key="baseline_run_id", value=run_id)


def run_hyperparameter_sweep(**context):
    """Train all non-baseline configs."""
    all_run_ids = []
    for n, d, l in PARAM_CONFIGS[1:]:
        run_id = train_single_run(n, d, l, **context)
        all_run_ids.append(run_id)
    context["ti"].xcom_push(key="sweep_run_ids", value=all_run_ids)


# ── Task 7: Promote best model ────────────────────────────────────────────────

def promote_best_model(**context):
    """Find the run with highest AUC-ROC and promote to Production."""
    import mlflow
    from mlflow import MlflowClient

    MODEL_REG_NAME  = "fleetguard-rf"
    EXPERIMENT_NAME = "fleetguard-predictive-maintenance"

    mlflow.set_tracking_uri(MLFLOW_URI)
    client = MlflowClient(tracking_uri=MLFLOW_URI)

    experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
    if not experiment:
        raise ValueError(f"Experiment '{EXPERIMENT_NAME}' not found in MLflow.")

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["metrics.auc_roc DESC"],
        max_results=1,
    )
    if not runs:
        raise ValueError("No MLflow runs found.")

    best = runs[0]
    best_auc = best.data.metrics.get("auc_roc", 0)
    best_run_id = best.info.run_id

    log.info(f"Best run: {best_run_id[:16]} | AUC={best_auc:.4f}")

    # Find and promote the model version for this run
    versions = client.search_model_versions(f"name='{MODEL_REG_NAME}'")
    promoted_version = None
    for v in versions:
        if v.run_id == best_run_id:
            client.transition_model_version_stage(
                name=MODEL_REG_NAME,
                version=v.version,
                stage="Production",
                archive_existing_versions=True,
            )
            promoted_version = v.version
            log.info(f"Promoted model v{v.version} to Production stage.")
            break

    # Push summary to XCom
    context["ti"].xcom_push(key="best_auc",     value=best_auc)
    context["ti"].xcom_push(key="best_run_id",  value=best_run_id)
    context["ti"].xcom_push(key="model_version", value=promoted_version)


# ── Task 8: Notify + save summary ─────────────────────────────────────────────

def notify_complete(**context):
    """Write a run summary JSON and log final metrics."""
    ti = context["ti"]
    run_date = context["ds"]

    best_auc     = ti.xcom_pull(task_ids="promote_best_model", key="best_auc")
    best_run_id  = ti.xcom_pull(task_ids="promote_best_model", key="best_run_id")
    model_version= ti.xcom_pull(task_ids="promote_best_model", key="model_version")
    tel_rows     = ti.xcom_pull(task_ids="export_telemetry",   key="telemetry_rows")
    new_rows     = ti.xcom_pull(task_ids="data_freshness",     key="new_rows")

    summary = {
        "run_date":      run_date,
        "telemetry_rows": tel_rows,
        "new_rows_7d":   new_rows,
        "best_run_id":   best_run_id,
        "best_auc_roc":  best_auc,
        "model_version": model_version,
        "promoted_to":   "Production",
    }

    summary_path = DATA_DIR / "reports" / f"retrain_summary_{run_date}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    log.info("=" * 55)
    log.info("  FleetGuard Retraining Complete")
    log.info("=" * 55)
    log.info(f"  Date:          {run_date}")
    log.info(f"  Telemetry:     {tel_rows:,} rows total")
    log.info(f"  New (7 days):  {new_rows:,}")
    log.info(f"  Best AUC-ROC:  {best_auc:.4f}")
    log.info(f"  Model version: v{model_version} → Production")
    log.info(f"  Summary saved: {summary_path}")
    log.info("=" * 55)


# ── Wire tasks into DAG ────────────────────────────────────────────────────────

t_freshness = ShortCircuitOperator(
    task_id="data_freshness",
    python_callable=check_data_freshness,
    dag=dag,
)

t_export = PythonOperator(
    task_id="export_telemetry",
    python_callable=export_telemetry_to_csv,
    dag=dag,
)

t_spark_prep = PythonOperator(
    task_id="spark_preprocessing",
    python_callable=run_spark_preprocessing,
    dag=dag,
)

t_spark_feat = PythonOperator(
    task_id="spark_feature_engineering",
    python_callable=run_spark_feature_engineering,
    dag=dag,
)

t_baseline = PythonOperator(
    task_id="train_baseline",
    python_callable=train_baseline,
    dag=dag,
)

t_sweep = PythonOperator(
    task_id="hyperparameter_sweep",
    python_callable=run_hyperparameter_sweep,
    dag=dag,
)

t_promote = PythonOperator(
    task_id="promote_best_model",
    python_callable=promote_best_model,
    dag=dag,
)

t_notify = PythonOperator(
    task_id="notify_complete",
    python_callable=notify_complete,
    dag=dag,
)

# ── Task dependency chain ──────────────────────────────────────────────────────
#
#   data_freshness → export_telemetry → spark_preprocessing
#                                             ↓
#                                  spark_feature_engineering
#                                             ↓
#                                       train_baseline
#                                             ↓
#                                   hyperparameter_sweep
#                                             ↓
#                                     promote_best_model
#                                             ↓
#                                       notify_complete

(
    t_freshness
    >> t_export
    >> t_spark_prep
    >> t_spark_feat
    >> t_baseline
    >> t_sweep
    >> t_promote
    >> t_notify
)
