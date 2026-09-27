"""
preprocessing.py — PySpark job: raw telemetry cleaning & validation.

Reads raw telemetry from PostgreSQL, applies data quality checks,
removes outliers, and writes a clean Parquet dataset.

Usage:
    python spark/preprocessing/preprocessing.py

Output:
    data/processed/telemetry_clean.parquet
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType

# ── Config ─────────────────────────────────────────────────────────────────────
DB_URL      = os.getenv("DATABASE_URL", "postgresql://fleetguard:fleetguard@localhost:5433/fleetguard")
JDBC_URL    = "jdbc:" + DB_URL
JDBC_DRIVER = "org.postgresql.Driver"
JDBC_JAR    = os.path.join(ROOT, "spark", "jars", "postgresql-42.7.3.jar")
OUTPUT_PATH = os.path.join(ROOT, "data", "processed", "telemetry_clean.parquet")

# Sensor healthy operating ranges (values outside → flag as anomaly, not drop)
BOUNDS = {
    "volt":      (50.0,  300.0),
    "rotate":    (0.0,   1000.0),
    "pressure":  (0.0,   300.0),
    "vibration": (0.0,   300.0),
}


def create_spark():
    builder = (
        SparkSession.builder
        .appName("FleetGuard-Preprocessing")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "8")
    )
    # Add JDBC driver jar if available
    if os.path.exists(JDBC_JAR):
        builder = builder.config("spark.driver.extraClassPath", JDBC_JAR)
    return builder.getOrCreate()


def load_telemetry(spark: SparkSession):
    """Load raw telemetry from PostgreSQL via JDBC."""
    if not os.path.exists(JDBC_JAR):
        print(f"[WARNING] JDBC jar not found at {JDBC_JAR}. Falling back to CSV export.")
        csv_path = os.path.join(ROOT, "data", "raw", "telemetry.csv")
        if not os.path.exists(csv_path):
            raise FileNotFoundError(
                f"No JDBC jar and no CSV fallback at {csv_path}. "
                "Run: python database/export_csv.py first."
            )
        return spark.read.csv(csv_path, header=True, inferSchema=True)

    return (
        spark.read
        .format("jdbc")
        .option("url", JDBC_URL)
        .option("dbtable", "telemetry")
        .option("driver", JDBC_DRIVER)
        .load()
    )


def load_machines(spark: SparkSession):
    """Load machine metadata from PostgreSQL via JDBC."""
    if not os.path.exists(JDBC_JAR):
        csv_path = os.path.join(ROOT, "data", "raw", "machines.csv")
        if os.path.exists(csv_path):
            return spark.read.csv(csv_path, header=True, inferSchema=True)
        return None

    return (
        spark.read
        .format("jdbc")
        .option("url", JDBC_URL)
        .option("dbtable", "machines")
        .option("driver", JDBC_DRIVER)
        .load()
    )


def clean(df):
    """
    Data quality cleaning:
    1. Drop nulls in sensor columns
    2. Cast all sensors to DoubleType
    3. Flag out-of-range readings (don't drop — could be real faults)
    4. Add data quality score column
    """
    sensor_cols = ["volt", "rotate", "pressure", "vibration"]

    # Cast to double
    for col in sensor_cols:
        df = df.withColumn(col, F.col(col).cast(DoubleType()))

    # Drop rows with null sensors or null machine_id
    df = df.dropna(subset=["machine_id"] + sensor_cols)

    # Flag out-of-range (anomaly indicator, not a reason to drop)
    anomaly_flags = []
    for col, (lo, hi) in BOUNDS.items():
        flag = F.when(
            (F.col(col) < lo) | (F.col(col) > hi), 1
        ).otherwise(0)
        df = df.withColumn(f"{col}_oob", flag)
        anomaly_flags.append(f"{col}_oob")

    # Data quality score: fraction of in-range sensors (1.0 = all good)
    df = df.withColumn(
        "dq_score",
        1.0 - (sum(F.col(f) for f in anomaly_flags) / len(anomaly_flags))
    )

    # Parse timestamp if string
    df = df.withColumn(
        "timestamp",
        F.coalesce(
            F.to_timestamp("timestamp", "yyyy-MM-dd HH:mm:ss"),
            F.to_timestamp("timestamp"),
        )
    )

    return df


def main():
    print("=" * 60)
    print("FleetGuard PySpark — Preprocessing Job")
    print("=" * 60)

    spark = create_spark()
    spark.sparkContext.setLogLevel("WARN")

    print("\n[1/4] Loading telemetry from PostgreSQL...")
    raw = load_telemetry(spark)
    raw_count = raw.count()
    print(f"      Loaded {raw_count:,} raw rows")

    print("[2/4] Cleaning & validating...")
    clean_df = clean(raw)
    clean_count = clean_df.count()
    dropped = raw_count - clean_count
    print(f"      Clean rows: {clean_count:,}  (dropped {dropped:,} nulls)")

    # Join machine metadata if available
    machines = load_machines(spark)
    if machines is not None:
        model_map = {"Model A": 0, "Model B": 1, "Model C": 2, "Model D": 3}
        # Add model_idx
        clean_df = clean_df.join(
            machines.select("machine_id", "model", "age"),
            on="machine_id",
            how="left"
        )
        print("[3/4] Joined machine metadata (model, age)")
    else:
        print("[3/4] Machine metadata not available, skipping join")

    print(f"[4/4] Writing clean Parquet to: {OUTPUT_PATH}")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    clean_df.write.mode("overwrite").parquet(OUTPUT_PATH)

    # Summary stats
    print("\n── Summary ──────────────────────────────────")
    clean_df.select(
        F.count("*").alias("total_rows"),
        F.countDistinct("machine_id").alias("unique_machines"),
        F.min("timestamp").alias("earliest"),
        F.max("timestamp").alias("latest"),
        F.avg("dq_score").alias("avg_dq_score"),
    ).show(truncate=False)

    print(f"\n✅ Preprocessing complete. Output: {OUTPUT_PATH}")
    spark.stop()


if __name__ == "__main__":
    main()
