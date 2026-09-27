"""
batch_inference.py — PySpark job: batch ML inference over historical telemetry.

Reads feature-engineered Parquet, runs the trained RandomForest model
via sklearn UDF (broadcast model to all workers), writes a per-machine
risk report as Parquet + CSV summary.

Usage:
    python spark/batch_inference/batch_inference.py

Input:
    data/processed/telemetry_features.parquet

Output:
    data/processed/batch_predictions.parquet
    data/reports/fleet_risk_report.csv
"""

import os
import sys
import pickle
import json

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, IntegerType
)

INPUT_PATH      = os.path.join(ROOT, "data", "processed", "telemetry_features.parquet")
PREDICTIONS_OUT = os.path.join(ROOT, "data", "processed", "batch_predictions.parquet")
REPORT_OUT      = os.path.join(ROOT, "data", "reports", "fleet_risk_report.csv")
MODEL_PATH      = os.path.join(ROOT, "ml", "model", "rf_model.pkl")
SCALER_PATH     = os.path.join(ROOT, "ml", "model", "scaler.pkl")

# The exact feature order the model was trained on
FEATURE_COLS = [
    "volt", "rotate", "pressure", "vibration",
    "volt_mean3h",      "volt_std3h",
    "rotate_mean3h",    "rotate_std3h",
    "pressure_mean3h",  "pressure_std3h",
    "vibration_mean3h", "vibration_std3h",
    "volt_mean24h",     "volt_std24h",
    "rotate_mean24h",   "rotate_std24h",
    "pressure_mean24h", "pressure_std24h",
    "vibration_mean24h","vibration_std24h",
    "error_error1_count", "error_error2_count", "error_error3_count",
    "error_error4_count", "error_error5_count",
    "model_idx", "age",
]


def create_spark():
    return (
        SparkSession.builder
        .appName("FleetGuard-BatchInference")
        .config("spark.driver.memory", "3g")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )


def load_model_artifacts():
    """Load sklearn model and scaler."""
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    scaler = None
    if os.path.exists(SCALER_PATH):
        with open(SCALER_PATH, "rb") as f:
            scaler = pickle.load(f)
    return model, scaler


def risk_label(prob: float) -> str:
    if prob >= 0.7:
        return "critical"
    elif prob >= 0.4:
        return "at_risk"
    return "healthy"


def make_predict_udf(model, scaler):
    """
    Create a Pandas UDF that applies the sklearn model to each row.
    The model and scaler are broadcast via closure.
    """
    import pandas as pd
    import numpy as np
    from pyspark.sql.functions import pandas_udf

    @pandas_udf(DoubleType())
    def predict_prob(*cols) -> "pd.Series":
        # Reconstruct the feature matrix from individual columns
        X = pd.concat(list(cols), axis=1).values.astype(float)
        if scaler is not None:
            try:
                X = scaler.transform(X)
            except Exception:
                pass
        probs = model.predict_proba(X)[:, 1]
        return pd.Series(probs)

    return predict_prob


def main():
    print("=" * 60)
    print("FleetGuard PySpark — Batch Inference Job")
    print("=" * 60)

    if not os.path.exists(INPUT_PATH):
        print(f"[ERROR] Features not found: {INPUT_PATH}")
        print("Run feature_engineering.py first.")
        sys.exit(1)

    print("\n[1/5] Loading model artifacts...")
    model, scaler = load_model_artifacts()
    print(f"      Model: {type(model).__name__}  |  Scaler: {type(scaler).__name__ if scaler else 'None'}")

    spark = create_spark()
    spark.sparkContext.setLogLevel("WARN")

    print(f"\n[2/5] Loading features from {INPUT_PATH}...")
    df = spark.read.parquet(INPUT_PATH)
    total = df.count()
    print(f"      Rows: {total:,}")

    # Ensure all feature columns present (fill missing with 0)
    for col in FEATURE_COLS:
        if col not in df.columns:
            df = df.withColumn(col, F.lit(0.0))

    print("[3/5] Running batch ML inference (sklearn RF via Pandas UDF)...")
    predict_udf = make_predict_udf(model, scaler)
    df = df.withColumn(
        "failure_probability",
        predict_udf(*[F.col(c).cast(DoubleType()) for c in FEATURE_COLS])
    )

    # Add risk level
    risk_udf = F.udf(risk_label, StringType())
    df = df.withColumn("risk_level", risk_udf(F.col("failure_probability")))

    print(f"[4/5] Writing predictions to {PREDICTIONS_OUT}...")
    os.makedirs(os.path.dirname(PREDICTIONS_OUT), exist_ok=True)
    out_cols = ["machine_id", "timestamp", "failure_probability", "risk_level"] + FEATURE_COLS
    out_cols = [c for c in out_cols if c in df.columns]
    df.select(out_cols).write.mode("overwrite").parquet(PREDICTIONS_OUT)

    print("[5/5] Generating fleet risk report...")
    os.makedirs(os.path.dirname(REPORT_OUT), exist_ok=True)

    report = df.groupBy("machine_id").agg(
        F.count("*").alias("total_readings"),
        F.avg("failure_probability").alias("avg_failure_prob"),
        F.max("failure_probability").alias("max_failure_prob"),
        F.min("failure_probability").alias("min_failure_prob"),
        F.sum(F.when(F.col("risk_level") == "critical", 1).otherwise(0)).alias("critical_ticks"),
        F.sum(F.when(F.col("risk_level") == "at_risk",  1).otherwise(0)).alias("at_risk_ticks"),
        F.sum(F.when(F.col("risk_level") == "healthy",  1).otherwise(0)).alias("healthy_ticks"),
        F.last("risk_level").alias("current_risk_level"),
        F.last("failure_probability").alias("current_failure_prob"),
    ).orderBy(F.col("avg_failure_prob").desc())

    # Write CSV report
    report_pd = report.toPandas()
    report_pd.to_csv(REPORT_OUT, index=False)

    print("\n── Fleet Risk Report (top 10 machines) ─────────────────")
    report.show(10, truncate=False)

    # Summary stats
    risk_dist = df.groupBy("risk_level").count().orderBy("risk_level")
    print("── Risk Distribution ────────────────────────────────────")
    risk_dist.show()

    print(f"\n✅ Batch inference complete.")
    print(f"   Predictions: {PREDICTIONS_OUT}")
    print(f"   Report:      {REPORT_OUT}")
    spark.stop()


if __name__ == "__main__":
    main()
