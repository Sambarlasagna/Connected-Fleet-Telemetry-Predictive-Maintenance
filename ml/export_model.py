"""
export_model.py

Re-trains a scikit-learn Random Forest on the same processed fleet data,
saves it as rf_model.pkl, and generates seed data for the PostgreSQL database.

Run from the project root:
    python ml/export_model.py
"""

import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, f1_score, classification_report
import warnings
warnings.filterwarnings("ignore")

# [OK][OK] Paths [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARQUET_PATH = os.path.join(ROOT, "data", "processed", "fleet_processed.parquet")
MODEL_DIR    = os.path.join(ROOT, "ml", "model")
SEED_DIR     = os.path.join(ROOT, "database", "seed")

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(SEED_DIR,  exist_ok=True)

# [OK][OK] Feature columns (same 27 as notebook) [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]

SENSORS = ["volt", "rotate", "pressure", "vibration"]

FEATURE_COLS = (
    SENSORS
    + [f"{s}_mean3h"  for s in SENSORS]
    + [f"{s}_std3h"   for s in SENSORS]
    + [f"{s}_mean24h" for s in SENSORS]
    + [f"{s}_std24h"  for s in SENSORS]
    + ["error_error1_count", "error_error2_count", "error_error3_count",
       "error_error4_count", "error_error5_count"]
    + ["model_idx", "age"]
)

print(f"Feature count: {len(FEATURE_COLS)}")
print(f"Features: {FEATURE_COLS}")

# [OK][OK] Load data [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]

print("\nLoading processed parquet...")
df = pd.read_parquet(PARQUET_PATH)
print(f"  Rows: {len(df):,}")
print(f"  Columns: {list(df.columns)}")
print(f"  Label distribution:\n{df['label'].value_counts()}")

# [OK][OK] Class balancing (same as notebook: 4:1 ratio) [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]

positives = df[df["label"] == 1]
negatives = df[df["label"] == 0]
ratio = len(positives) * 4 / len(negatives)
negatives_sampled = negatives.sample(frac=min(ratio, 1.0), random_state=42)
balanced = pd.concat([positives, negatives_sampled]).sample(frac=1, random_state=42)

print(f"\nBalanced dataset: {len(balanced):,} rows")
print(f"  Positives: {len(balanced[balanced['label']==1]):,} ({100*len(balanced[balanced['label']==1])/len(balanced):.1f}%)")

# [OK][OK] Chronological split (same as notebook: 80/20 by timestamp) [OK][OK][OK][OK][OK][OK][OK][OK]

cutoff = balanced["ts"].quantile(0.8)
train_df = balanced[balanced["ts"] <= cutoff]
test_df  = balanced[balanced["ts"] >  cutoff]

X_train = train_df[FEATURE_COLS].values
y_train = train_df["label"].values
X_test  = test_df[FEATURE_COLS].values
y_test  = test_df["label"].values

print(f"\nTrain: {len(X_train):,}  |  Test: {len(X_test):,}")

# [OK][OK] Train sklearn Random Forest [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]

print("\nTraining sklearn RandomForest...")
model = Pipeline([
    ("scaler", StandardScaler()),
    ("rf", RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        min_samples_leaf=10,
        max_features="sqrt",
        random_state=42,
        n_jobs=-1,
    ))
])

model.fit(X_train, y_train)
print("Training complete [OK]")

# [OK][OK] Evaluate [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]

y_pred  = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

auc = roc_auc_score(y_test, y_proba)
f1  = f1_score(y_test, y_pred)
print(f"\nTest AUC-ROC : {auc:.4f}")
print(f"Test F1      : {f1:.4f}")
print(classification_report(y_test, y_pred, target_names=["Normal", "Failure"]))

# [OK][OK] Save model + metadata [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]

model_path = os.path.join(MODEL_DIR, "rf_model.pkl")
with open(model_path, "wb") as f:
    pickle.dump(model, f)
print(f"\nModel saved [OK] {model_path}")

meta = {
    "feature_cols": FEATURE_COLS,
    "auc_roc": round(auc, 4),
    "f1_score": round(f1, 4),
    "n_estimators": 100,
    "max_depth": 8,
}
meta_path = os.path.join(MODEL_DIR, "model_meta.json")
with open(meta_path, "w") as f:
    json.dump(meta, f, indent=2)
print(f"Metadata saved [OK] {meta_path}")

# [OK][OK] Generate seed data [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]
# For each machine (1[OK]100), get the LATEST row of features and run prediction.

print("\nGenerating seed data for database...")

# Load the FULL (unbalanced) dataset to get real latest readings per machine
full_df = pd.read_parquet(PARQUET_PATH)

# Sort by machine + timestamp, take last row per machine
latest = (
    full_df
    .sort_values(["machineID", "ts"])
    .groupby("machineID")
    .last()
    .reset_index()
)

# Run predictions
X_latest = latest[FEATURE_COLS].values
probs = model.predict_proba(X_latest)[:, 1]
latest["failure_probability"] = probs

def risk_level(p):
    if p >= 0.7:
        return "critical"
    elif p >= 0.4:
        return "at_risk"
    else:
        return "healthy"

def recommended_action(level):
    return {
        "critical": "Schedule immediate maintenance inspection.",
        "at_risk":  "Monitor closely [OK] maintenance recommended within 48 hours.",
        "healthy":  "No action required. Continue normal operation.",
    }[level]

latest["risk_level"] = latest["failure_probability"].apply(risk_level)
latest["recommended_action"] = latest["risk_level"].apply(recommended_action)

print(f"  Risk distribution:\n{latest['risk_level'].value_counts()}")

# [OK][OK] SHAP values per machine [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]

print("\nComputing SHAP values for each machine...")
try:
    import shap
    rf_model = model.named_steps["rf"]
    scaler   = model.named_steps["scaler"]
    X_scaled = scaler.transform(X_latest)
    explainer = shap.TreeExplainer(rf_model)
    shap_values = explainer.shap_values(X_scaled)
    # Handle both old list API and new 3D array API
    if isinstance(shap_values, list):
        shap_class1 = np.array(shap_values[1])   # (n_samples, n_features)
    elif hasattr(shap_values, 'values'):
        sv = shap_values.values                   # Explanation object
        shap_class1 = sv[:, :, 1] if sv.ndim == 3 else sv
    else:
        sv = np.array(shap_values)
        shap_class1 = sv[:, :, 1] if sv.ndim == 3 else sv
    print(f"SHAP shape: {shap_class1.shape}")
    print("SHAP computed [OK]")
    has_shap = True
except Exception as e:
    print(f"SHAP not available: {e}. Using feature importances as fallback.")
    has_shap = False
    importances = model.named_steps["rf"].feature_importances_

# [OK][OK] Build seed JSON files [OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK][OK]

# Load machines CSV for model/age metadata
machines_csv = os.path.join(ROOT, "data", "raw", "PdM_machines.csv")
machines_meta = pd.read_csv(machines_csv)

# Model column is text like 'model1', 'model2', etc.
def map_model_name(val):
    mapping = {"model1": "Model A", "model2": "Model B", "model3": "Model C", "model4": "Model D"}
    return mapping.get(str(val), str(val).replace("model", "Model ").title())

machines_meta["model_name"] = machines_meta["model"].apply(map_model_name)

# Merge
latest = latest.merge(
    machines_meta[["machineID", "model", "age", "model_name"]],
    on="machineID", how="left", suffixes=("", "_meta")
)

machines_seed = []
predictions_seed = []
telemetry_seed = []

latest = latest.reset_index(drop=True)

for i, row in latest.iterrows():
    mid = int(row["machineID"])

    model_display = row.get("model_name") or f"Model {row.get('model', 'Unknown')}"

    # Machine record
    machines_seed.append({
        "machine_id": mid,
        "machine_name": f"Machine {mid:03d}",
        "model": str(model_display),
        "age": int(row.get("age_meta", row.get("age", 0))),
        "risk_level": row["risk_level"],
        "failure_probability": round(float(row["failure_probability"]), 4),
    })

    # Prediction record with SHAP
    if has_shap:
        shap_row = np.array(shap_class1[i]).ravel()  # ensure 1D (n_features,)
        explanation = {
            feat: round(float(val), 4)
            for feat, val in zip(FEATURE_COLS, shap_row)
        }
        # Top 5 by absolute value
        top5 = dict(sorted(explanation.items(), key=lambda x: abs(x[1]), reverse=True)[:5])
    else:
        top5 = {
            feat: round(float(importances[j]), 4)
            for j, feat in enumerate(FEATURE_COLS)
        }
        top5 = dict(sorted(top5.items(), key=lambda x: abs(x[1]), reverse=True)[:5])

    predictions_seed.append({
        "machine_id": mid,
        "failure_probability": round(float(row["failure_probability"]), 4),
        "risk_level": row["risk_level"],
        "recommended_action": row["recommended_action"],
        "explanation": top5,
    })

    # Latest telemetry row
    telemetry_seed.append({
        "machine_id": mid,
        "timestamp": str(pd.Timestamp(int(row["ts"]), unit="s")),
        "volt": round(float(row["volt"]), 2),
        "rotate": round(float(row["rotate"]), 2),
        "pressure": round(float(row["pressure"]), 2),
        "vibration": round(float(row["vibration"]), 2),
    })

# Save seed files
with open(os.path.join(SEED_DIR, "machines.json"), "w") as f:
    json.dump(machines_seed, f, indent=2)

with open(os.path.join(SEED_DIR, "predictions.json"), "w") as f:
    json.dump(predictions_seed, f, indent=2)

with open(os.path.join(SEED_DIR, "telemetry_latest.json"), "w") as f:
    json.dump(telemetry_seed, f, indent=2)

print(f"\nSeed data saved to {SEED_DIR}/")
print(f"  machines.json       ({len(machines_seed)} records)")
print(f"  predictions.json    ({len(predictions_seed)} records)")
print(f"  telemetry_latest.json ({len(telemetry_seed)} records)")
print("\n[OK] All done! Model and seed data ready.")
