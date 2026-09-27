"""
feature_engineering.py — PySpark job: rolling window feature engineering.

Reads clean Parquet telemetry, computes the same rolling window features
(3h, 24h) that the ML model expects, and writes a feature-engineered
dataset ready for batch inference or model retraining.

Usage:
    python spark/feature_engineering/feature_engineering.py

Input:
    data/processed/telemetry_clean.parquet

Output:
    data/processed/telemetry_features.parquet
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType

INPUT_PATH  = os.path.join(ROOT, "data", "processed", "telemetry_clean.parquet")
OUTPUT_PATH = os.path.join(ROOT, "data", "processed", "telemetry_features.parquet")

# Rolling window sizes in seconds
WIN_3H  = 3 * 60 * 60    # 3 hours
WIN_24H = 24 * 60 * 60   # 24 hours

# Model map (must match training)
MODEL_MAP = {"Model A": 0, "Model B": 1, "Model C": 2, "Model D": 3}


def create_spark():
    return (
        SparkSession.builder
        .appName("FleetGuard-FeatureEngineering")
        .config("spark.driver.memory", "3g")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )


def rolling_stats(df, sensor_col: str, window_seconds: int, suffix: str):
    """
    Add mean and std of `sensor_col` over a trailing time window per machine.
    Uses a row-based approximation (ordered rows within partition).
    """
    w = (
        Window
        .partitionBy("machine_id")
        .orderBy(F.col("ts_unix").cast("long"))
        .rangeBetween(-window_seconds, 0)
    )
    df = df.withColumn(f"{sensor_col}_mean{suffix}", F.avg(F.col(sensor_col)).over(w))
    df = df.withColumn(f"{sensor_col}_std{suffix}",  F.stddev(F.col(sensor_col)).over(w))
    return df


def engineer_features(df):
    """Build full feature vector matching the trained RF model."""
    sensors = ["volt", "rotate", "pressure", "vibration"]

    # Unix timestamp for range windows
    df = df.withColumn("ts_unix", F.unix_timestamp("timestamp"))

    # 3h rolling stats
    for s in sensors:
        df = rolling_stats(df, s, WIN_3H,  "3h")

    # 24h rolling stats
    for s in sensors:
        df = rolling_stats(df, s, WIN_24H, "24h")

    # Fill nulls from rolling (first rows won't have a full window)
    for s in sensors:
        for suffix in ["3h", "24h"]:
            df = df.fillna({f"{s}_mean{suffix}": 0.0, f"{s}_std{suffix}": 0.0})

    # Error counts (placeholder — 0 for DB-sourced data)
    for i in range(1, 6):
        df = df.withColumn(f"error_error{i}_count", F.lit(0.0))

    # Machine metadata encoding
    if "model" in df.columns:
        mapping_expr = F.create_map(
            *[item for pair in [(F.lit(k), F.lit(v)) for k, v in MODEL_MAP.items()] for item in pair]
        )
        df = df.withColumn("model_idx", mapping_expr[F.col("model")].cast("double"))
        df = df.fillna({"model_idx": 0.0})
    else:
        df = df.withColumn("model_idx", F.lit(0.0))

    if "age" not in df.columns:
        df = df.withColumn("age", F.lit(5.0))

    df = df.withColumn("age", F.col("age").cast("double"))

    return df


def main():
    print("=" * 60)
    print("FleetGuard PySpark — Feature Engineering Job")
    print("=" * 60)

    if not os.path.exists(INPUT_PATH):
        print(f"[ERROR] Input not found: {INPUT_PATH}")
        print("Run preprocessing.py first.")
        sys.exit(1)

    spark = create_spark()
    spark.sparkContext.setLogLevel("WARN")

    print(f"\n[1/3] Loading clean telemetry from {INPUT_PATH}...")
    df = spark.read.parquet(INPUT_PATH)
    print(f"      Rows: {df.count():,}  Machines: {df.select('machine_id').distinct().count()}")

    print("[2/3] Engineering rolling window features (3h + 24h)...")
    featured = engineer_features(df)

    # Feature columns expected by the model
    feature_cols = (
        ["machine_id", "timestamp", "volt", "rotate", "pressure", "vibration"] +
        [f"{s}_mean3h"  for s in ["volt","rotate","pressure","vibration"]] +
        [f"{s}_std3h"   for s in ["volt","rotate","pressure","vibration"]] +
        [f"{s}_mean24h" for s in ["volt","rotate","pressure","vibration"]] +
        [f"{s}_std24h"  for s in ["volt","rotate","pressure","vibration"]] +
        [f"error_error{i}_count" for i in range(1, 6)] +
        ["model_idx", "age"]
    )
    # Keep only columns that exist
    existing = [c for c in feature_cols if c in featured.columns]
    output = featured.select(existing)

    print(f"      Feature columns: {len(existing)}")

    print(f"[3/3] Writing features to {OUTPUT_PATH}...")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    output.write.mode("overwrite").parquet(OUTPUT_PATH)

    print("\n── Sample features ──────────────────────────────────")
    output.select(
        "machine_id", "timestamp", "volt", "vibration",
        "vibration_mean3h", "vibration_std3h", "vibration_mean24h"
    ).show(5, truncate=True)

    print(f"\n✅ Feature engineering complete. Output: {OUTPUT_PATH}")
    spark.stop()


if __name__ == "__main__":
    main()
