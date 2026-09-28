"""
hyperparameter_sweep.py — Grid search over RF hyperparameters, each run
tracked as a separate MLflow experiment run. The best model (highest AUC)
is automatically promoted to "Production" in the Model Registry.

Usage:
    python ml/training/hyperparameter_sweep.py
"""

import os
import sys
import warnings
warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import mlflow
from mlflow import MlflowClient
from ml.training.train_with_mlflow import train, MLFLOW_URI, EXPERIMENT_NAME, MODEL_REG_NAME

# Grid of hyperparameter combinations to try
PARAM_GRID = [
    {"n_estimators": 50,  "max_depth": 6,  "min_samples_leaf": 10},
    {"n_estimators": 100, "max_depth": 8,  "min_samples_leaf": 10},   # baseline
    {"n_estimators": 100, "max_depth": 10, "min_samples_leaf": 5},
    {"n_estimators": 200, "max_depth": 8,  "min_samples_leaf": 10},
    {"n_estimators": 200, "max_depth": 12, "min_samples_leaf": 5},
]


def promote_best_model():
    """Find the run with highest AUC-ROC and transition it to Production."""
    client = MlflowClient(tracking_uri=MLFLOW_URI)

    experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
    if not experiment:
        print("[Warning] Experiment not found, skipping promotion.")
        return

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["metrics.auc_roc DESC"],
        max_results=1,
    )

    if not runs:
        print("[Warning] No runs found.")
        return

    best = runs[0]
    best_auc = best.data.metrics.get("auc_roc", 0)
    best_run_id = best.info.run_id

    print(f"\n{'='*60}")
    print(f"  Best run: {best_run_id[:16]}...")
    print(f"  Best AUC-ROC: {best_auc:.4f}")

    # Find all versions of the registered model
    try:
        versions = client.search_model_versions(f"name='{MODEL_REG_NAME}'")
        # Transition the version from this run to Production
        for v in versions:
            if v.run_id == best_run_id:
                client.transition_model_version_stage(
                    name=MODEL_REG_NAME,
                    version=v.version,
                    stage="Production",
                    archive_existing_versions=True,
                )
                print(f"  ✅ Model v{v.version} promoted to Production")
                break
    except Exception as e:
        print(f"  [Info] Model Registry promotion: {e}")

    print(f"{'='*60}\n")


def main():
    print("\n" + "="*60)
    print("  FleetGuard — Hyperparameter Sweep")
    print(f"  Runs to execute: {len(PARAM_GRID)}")
    print("="*60)

    results = []
    for i, params in enumerate(PARAM_GRID):
        print(f"\n── Run {i+1}/{len(PARAM_GRID)}: {params} ──")
        try:
            metrics, run_id = train(**params)
            results.append({"run_id": run_id, "params": params, **metrics})
        except Exception as e:
            print(f"[ERROR] Run failed: {e}")

    # Summary
    print("\n── Sweep Results ────────────────────────────────────────")
    print(f"{'Params':<45} {'AUC':>7} {'F1':>7}")
    print("-" * 62)
    results.sort(key=lambda r: r["auc_roc"], reverse=True)
    for r in results:
        p = r["params"]
        label = f"n={p['n_estimators']} d={p['max_depth']} leaf={p['min_samples_leaf']}"
        print(f"{label:<45} {r['auc_roc']:.4f}  {r['f1']:.4f}")

    print("\n── Promoting best model to Production ───────────────────")
    promote_best_model()

    print("View all runs: mlflow ui --host 127.0.0.1 --port 5000")


if __name__ == "__main__":
    main()
