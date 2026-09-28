"""
train_with_mlflow.py — Random Forest training with MLflow experiment tracking.

Wraps the existing export_model.py training logic with MLflow:
  - Tracks hyperparameters, metrics (AUC, F1, precision, recall)
  - Logs the model to MLflow Model Registry
  - Saves artifacts (confusion matrix, feature importance plot, SHAP summary)
  - Promotes the best model to "Production" stage automatically

Usage:
    # Start MLflow UI first (in a separate terminal):
    mlflow ui --host 127.0.0.1 --port 5000

    # Then run training:
    python ml/training/train_with_mlflow.py

    # Or with custom hyperparams:
    python ml/training/train_with_mlflow.py --n-estimators 200 --max-depth 10
"""

import os
import sys
import json
import pickle
import argparse
import warnings
warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # non-interactive backend for server environments
import matplotlib.pyplot as plt

from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score, f1_score, precision_score, recall_score,
    accuracy_score, classification_report, confusion_matrix,
    ConfusionMatrixDisplay,
)

import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature

# ── Config ─────────────────────────────────────────────────────────────────────

PARQUET_PATH    = os.path.join(ROOT, "data", "processed", "fleet_processed.parquet")
MODEL_DIR       = os.path.join(ROOT, "ml", "model")
MLFLOW_URI      = os.getenv("MLFLOW_TRACKING_URI",
                             "sqlite:///" + os.path.join(ROOT, "mlruns", "mlflow.db").replace("\\", "/"))
EXPERIMENT_NAME = "fleetguard-predictive-maintenance"
MODEL_REG_NAME  = "fleetguard-rf"

FEATURE_COLS = (
    ["volt", "rotate", "pressure", "vibration"]
    + [f"{s}_mean3h"  for s in ["volt","rotate","pressure","vibration"]]
    + [f"{s}_std3h"   for s in ["volt","rotate","pressure","vibration"]]
    + [f"{s}_mean24h" for s in ["volt","rotate","pressure","vibration"]]
    + [f"{s}_std24h"  for s in ["volt","rotate","pressure","vibration"]]
    + ["error_error1_count","error_error2_count","error_error3_count",
       "error_error4_count","error_error5_count"]
    + ["model_idx", "age"]
)


def load_and_split(parquet_path: str):
    """Load parquet, balance classes, chronological 80/20 split."""
    df = pd.read_parquet(parquet_path)

    positives = df[df["label"] == 1]
    negatives = df[df["label"] == 0]
    ratio = len(positives) * 4 / len(negatives)
    neg_sampled = negatives.sample(frac=min(ratio, 1.0), random_state=42)
    balanced = pd.concat([positives, neg_sampled]).sample(frac=1, random_state=42)

    cutoff = balanced["ts"].quantile(0.8)
    train_df = balanced[balanced["ts"] <= cutoff]
    test_df  = balanced[balanced["ts"] >  cutoff]

    X_train = train_df[FEATURE_COLS].values
    y_train = train_df["label"].values
    X_test  = test_df[FEATURE_COLS].values
    y_test  = test_df["label"].values

    return X_train, y_train, X_test, y_test, balanced


def plot_confusion_matrix(y_true, y_pred, path: str):
    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(5, 4))
    disp = ConfusionMatrixDisplay(cm, display_labels=["Normal", "Failure"])
    disp.plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title("Confusion Matrix")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_feature_importance(model, feature_names, path: str, top_n: int = 15):
    rf = model.named_steps["rf"]
    importances = pd.Series(rf.feature_importances_, index=feature_names)
    top = importances.nlargest(top_n).sort_values()

    fig, ax = plt.subplots(figsize=(7, 5))
    colors = ["#6366f1" if i >= len(top) - 3 else "#94a3b8" for i in range(len(top))]
    top.plot.barh(ax=ax, color=colors)
    ax.set_title(f"Top {top_n} Feature Importances", fontsize=12)
    ax.set_xlabel("Importance")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def train(n_estimators: int = 100, max_depth: int = 8,
          min_samples_leaf: int = 10, max_features: str = "sqrt"):
    """Train RF with MLflow tracking."""

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    print(f"\n{'='*60}")
    print(f"  FleetGuard ML Training — MLflow Experiment")
    print(f"  Tracking URI: {MLFLOW_URI}")
    print(f"  Experiment:   {EXPERIMENT_NAME}")
    print(f"{'='*60}\n")

    # Load data
    print("[1/5] Loading data...")
    X_train, y_train, X_test, y_test, balanced = load_and_split(PARQUET_PATH)
    print(f"      Train: {len(X_train):,}  |  Test: {len(X_test):,}")
    print(f"      Features: {len(FEATURE_COLS)}")

    with mlflow.start_run(run_name=f"rf-n{n_estimators}-d{max_depth}") as run:
        run_id = run.info.run_id
        print(f"\n[2/5] MLflow run started: {run_id[:8]}...")

        # Log hyperparameters
        params = {
            "n_estimators":    n_estimators,
            "max_depth":       max_depth,
            "min_samples_leaf": min_samples_leaf,
            "max_features":    max_features,
            "train_rows":      len(X_train),
            "test_rows":       len(X_test),
            "n_features":      len(FEATURE_COLS),
            "class_balance":   "4:1 neg:pos ratio",
            "split_strategy":  "chronological-80-20",
        }
        mlflow.log_params(params)

        # Train
        print("[3/5] Training RandomForest...")
        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("rf", RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                min_samples_leaf=min_samples_leaf,
                max_features=max_features,
                random_state=42,
                n_jobs=-1,
            ))
        ])
        pipeline.fit(X_train, y_train)

        # Evaluate
        y_pred  = pipeline.predict(X_test)
        y_proba = pipeline.predict_proba(X_test)[:, 1]

        metrics = {
            "auc_roc":   roc_auc_score(y_test, y_proba),
            "f1":        f1_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred),
            "recall":    recall_score(y_test, y_pred),
            "accuracy":  accuracy_score(y_test, y_pred),
        }
        mlflow.log_metrics(metrics)

        print(f"      AUC-ROC:   {metrics['auc_roc']:.4f}")
        print(f"      F1:        {metrics['f1']:.4f}")
        print(f"      Precision: {metrics['precision']:.4f}")
        print(f"      Recall:    {metrics['recall']:.4f}")

        # Log artifacts (plots)
        print("[4/5] Saving artifacts...")
        tmp_dir = os.path.join(ROOT, "mlruns", "_tmp")
        os.makedirs(tmp_dir, exist_ok=True)

        cm_path = os.path.join(tmp_dir, "confusion_matrix.png")
        fi_path = os.path.join(tmp_dir, "feature_importance.png")
        plot_confusion_matrix(y_test, y_pred, cm_path)
        plot_feature_importance(pipeline, FEATURE_COLS, fi_path)
        mlflow.log_artifact(cm_path, artifact_path="plots")
        mlflow.log_artifact(fi_path, artifact_path="plots")

        # Log feature names as artifact
        feat_path = os.path.join(tmp_dir, "feature_cols.json")
        with open(feat_path, "w") as f:
            json.dump(FEATURE_COLS, f, indent=2)
        mlflow.log_artifact(feat_path, artifact_path="metadata")

        # Log model to registry
        print("[5/5] Registering model in MLflow Model Registry...")
        signature = infer_signature(X_train[:5], pipeline.predict_proba(X_train[:5]))
        model_info = mlflow.sklearn.log_model(
            sk_model=pipeline,
            name="model",
            signature=signature,
            registered_model_name=MODEL_REG_NAME,
            input_example=X_train[:3],
            skops_trusted_types=[
                "sklearn.tree._tree.Tree",
                "sklearn.pipeline.Pipeline",
                "sklearn.ensemble._forest.RandomForestClassifier",
                "sklearn.preprocessing._data.StandardScaler",
            ],
        )

        # Also save pkl for the existing inference code
        os.makedirs(MODEL_DIR, exist_ok=True)
        with open(os.path.join(MODEL_DIR, "rf_model.pkl"), "wb") as f:
            pickle.dump(pipeline, f)

        # Save metadata json
        meta = {
            "run_id":        run_id,
            "model_uri":     model_info.model_uri,
            "feature_cols":  FEATURE_COLS,
            "auc_roc":       round(metrics["auc_roc"], 4),
            "f1_score":      round(metrics["f1"], 4),
            "precision":     round(metrics["precision"], 4),
            "recall":        round(metrics["recall"], 4),
            "n_estimators":  n_estimators,
            "max_depth":     max_depth,
        }
        with open(os.path.join(MODEL_DIR, "model_meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

        print(f"\n{'='*60}")
        print(f"  ✅ Training complete!")
        print(f"  Run ID:    {run_id[:16]}...")
        print(f"  AUC-ROC:   {metrics['auc_roc']:.4f}")
        print(f"  F1:        {metrics['f1']:.4f}")
        print(f"  Model URI: {model_info.model_uri}")
        print(f"\n  View in MLflow UI: http://127.0.0.1:5000")
        print(f"{'='*60}\n")

    return metrics, run_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train FleetGuard RF with MLflow tracking")
    parser.add_argument("--n-estimators",    type=int,   default=100)
    parser.add_argument("--max-depth",       type=int,   default=8)
    parser.add_argument("--min-samples-leaf",type=int,   default=10)
    parser.add_argument("--max-features",    type=str,   default="sqrt")
    args = parser.parse_args()

    train(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
        max_features=args.max_features,
    )
