"""
mlflow_info.py — FastAPI route exposing MLflow model registry info.

GET /api/mlflow/model    → current Production model metadata
GET /api/mlflow/runs     → recent experiment runs (metrics + params)
GET /api/mlflow/best     → single best run by AUC
"""

import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

MLFLOW_URI      = os.getenv("MLFLOW_TRACKING_URI",
                             "sqlite:///" + os.path.join(ROOT, "mlruns", "mlflow.db").replace("\\", "/"))
EXPERIMENT_NAME = "fleetguard-predictive-maintenance"
MODEL_REG_NAME  = "fleetguard-rf"
MODEL_META_PATH = os.path.join(ROOT, "ml", "model", "model_meta.json")


def _get_client():
    try:
        import mlflow
        from mlflow import MlflowClient
        mlflow.set_tracking_uri(MLFLOW_URI)
        return MlflowClient(tracking_uri=MLFLOW_URI)
    except ImportError:
        return None


@router.get("/mlflow/model")
def get_model_info():
    """Return current production model metadata (from local json + MLflow registry)."""
    result = {
        "tracking_uri": MLFLOW_URI,
        "experiment":   EXPERIMENT_NAME,
        "registry_name": MODEL_REG_NAME,
        "meta": None,
        "production_version": None,
    }

    # Local metadata (always available)
    if os.path.exists(MODEL_META_PATH):
        with open(MODEL_META_PATH) as f:
            result["meta"] = json.load(f)

    # MLflow registry (if available)
    client = _get_client()
    if client:
        try:
            versions = client.search_model_versions(f"name='{MODEL_REG_NAME}'")
            prod = [v for v in versions if v.current_stage == "Production"]
            if prod:
                v = prod[0]
                result["production_version"] = {
                    "version":    v.version,
                    "run_id":     v.run_id,
                    "stage":      v.current_stage,
                    "created_at": v.creation_timestamp,
                }
        except Exception as e:
            result["registry_error"] = str(e)

    return result


@router.get("/mlflow/runs")
def get_runs(limit: int = 10):
    """Return the most recent MLflow experiment runs with metrics."""
    client = _get_client()
    if not client:
        return {"error": "MLflow not available", "runs": []}

    try:
        experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
        if not experiment:
            return {"runs": [], "message": "No experiments found. Run training first."}

        runs = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=["start_time DESC"],
            max_results=limit,
        )

        return {
            "experiment_id": experiment.experiment_id,
            "runs": [
                {
                    "run_id":     r.info.run_id[:12],
                    "run_name":   r.info.run_name,
                    "status":     r.info.status,
                    "start_time": r.info.start_time,
                    "metrics": {
                        "auc_roc":   round(r.data.metrics.get("auc_roc", 0), 4),
                        "f1":        round(r.data.metrics.get("f1", 0), 4),
                        "precision": round(r.data.metrics.get("precision", 0), 4),
                        "recall":    round(r.data.metrics.get("recall", 0), 4),
                        "accuracy":  round(r.data.metrics.get("accuracy", 0), 4),
                    },
                    "params": {
                        "n_estimators":    r.data.params.get("n_estimators"),
                        "max_depth":       r.data.params.get("max_depth"),
                        "min_samples_leaf": r.data.params.get("min_samples_leaf"),
                        "train_rows":      r.data.params.get("train_rows"),
                    },
                }
                for r in runs
            ]
        }
    except Exception as e:
        return {"error": str(e), "runs": []}


@router.get("/mlflow/best")
def get_best_run():
    """Return the single best run by AUC-ROC."""
    client = _get_client()
    if not client:
        return {"error": "MLflow not available"}

    try:
        experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
        if not experiment:
            return {"message": "No experiments found."}

        runs = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=["metrics.auc_roc DESC"],
            max_results=1,
        )
        if not runs:
            return {"message": "No runs found."}

        r = runs[0]
        return {
            "run_id":   r.info.run_id,
            "run_name": r.info.run_name,
            "metrics":  r.data.metrics,
            "params":   r.data.params,
        }
    except Exception as e:
        return {"error": str(e)}
