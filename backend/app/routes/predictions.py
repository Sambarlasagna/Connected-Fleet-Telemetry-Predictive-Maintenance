"""
predictions.py — Prediction + SHAP explainability endpoint.

GET /api/vehicles/{machine_id}/prediction
  Returns the latest stored prediction. If the explanation is empty
  (sim wrote a fast-path row with no SHAP), computes SHAP on-the-fly
  from the machine's latest telemetry + stored feature stats.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.connection import get_db
from app.models.schemas import PredictionResponse
from app.services.ml_service import predict, get_feature_cols
import json

router = APIRouter()


@router.get("/vehicles/{machine_id}/prediction", response_model=PredictionResponse)
def get_prediction(machine_id: int, db: Session = Depends(get_db)):
    """
    Current failure prediction + SHAP explanation for a machine.
    If the latest prediction has no SHAP (written by the fast simulator),
    we recompute it from the latest telemetry row.
    """
    row = db.execute(text("""
        SELECT machine_id, failure_probability, risk_level, recommended_action, explanation
        FROM predictions
        WHERE machine_id = :mid
        ORDER BY id DESC
        LIMIT 1
    """), {"mid": machine_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Prediction not found")

    explanation = row.explanation
    if isinstance(explanation, str):
        explanation = json.loads(explanation)

    # If explanation is empty (fast-path sim row), recompute with SHAP
    if not explanation:
        explanation = _compute_shap_for_machine(machine_id, db)

    return PredictionResponse(
        machine_id=row.machine_id,
        failure_probability=row.failure_probability,
        risk_level=row.risk_level,
        recommended_action=row.recommended_action,
        explanation=explanation,
    )


def _compute_shap_for_machine(machine_id: int, db: Session) -> dict:
    """
    Build a feature vector from the machine's latest telemetry + DB stats,
    then run full predict() (with SHAP) and return the explanation.
    Falls back to empty dict on any error.
    """
    try:
        # Fetch machine metadata
        m = db.execute(text("""
            SELECT model, age FROM machines WHERE machine_id = :mid
        """), {"mid": machine_id}).fetchone()

        if not m:
            return {}

        model_map = {"Model A": 0, "Model B": 1, "Model C": 2, "Model D": 3}
        model_idx = float(model_map.get(m.model, 0))
        age = float(m.age)

        # Latest telemetry reading
        t = db.execute(text("""
            SELECT volt, rotate, pressure, vibration
            FROM telemetry
            WHERE machine_id = :mid
            ORDER BY timestamp DESC
            LIMIT 1
        """), {"mid": machine_id}).fetchone()

        if not t:
            return {}

        # Rolling stats from last 50 rows (approximates 3h window)
        stats = db.execute(text("""
            SELECT
                AVG(volt)      AS volt_mean,   STDDEV(volt)      AS volt_std,
                AVG(rotate)    AS rot_mean,    STDDEV(rotate)    AS rot_std,
                AVG(pressure)  AS pres_mean,   STDDEV(pressure)  AS pres_std,
                AVG(vibration) AS vib_mean,    STDDEV(vibration) AS vib_std
            FROM (
                SELECT volt, rotate, pressure, vibration
                FROM telemetry
                WHERE machine_id = :mid
                ORDER BY timestamp DESC
                LIMIT 50
            ) sub
        """), {"mid": machine_id}).fetchone()

        def s(v):
            return float(v) if v is not None else 0.0

        features = {
            # Raw sensors
            "volt":      float(t.volt),
            "rotate":    float(t.rotate),
            "pressure":  float(t.pressure),
            "vibration": float(t.vibration),
            # 3h rolling (approx from last 50 rows)
            "volt_mean3h":      s(stats.volt_mean),
            "volt_std3h":       s(stats.volt_std),
            "rotate_mean3h":    s(stats.rot_mean),
            "rotate_std3h":     s(stats.rot_std),
            "pressure_mean3h":  s(stats.pres_mean),
            "pressure_std3h":   s(stats.pres_std),
            "vibration_mean3h": s(stats.vib_mean),
            "vibration_std3h":  s(stats.vib_std),
            # 24h rolling (same approximation — best we can do from DB)
            "volt_mean24h":      s(stats.volt_mean),
            "volt_std24h":       s(stats.volt_std),
            "rotate_mean24h":    s(stats.rot_mean),
            "rotate_std24h":     s(stats.rot_std),
            "pressure_mean24h":  s(stats.pres_mean),
            "pressure_std24h":   s(stats.pres_std),
            "vibration_mean24h": s(stats.vib_mean),
            "vibration_std24h":  s(stats.vib_std),
            # Error counts — zero for DB-derived features
            "error_error1_count": 0.0,
            "error_error2_count": 0.0,
            "error_error3_count": 0.0,
            "error_error4_count": 0.0,
            "error_error5_count": 0.0,
            # Machine metadata
            "model_idx": model_idx,
            "age":       age,
        }

        _, _, _, explanation = predict(features)
        return explanation

    except Exception as e:
        print(f"[predictions] SHAP recompute error for machine {machine_id}: {e}")
        return {}
