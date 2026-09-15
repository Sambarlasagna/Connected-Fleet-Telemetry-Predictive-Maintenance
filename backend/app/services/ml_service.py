"""
ML service — loads the trained sklearn Random Forest and runs inference + SHAP.
Model is loaded once at startup and cached for the lifetime of the server.
"""

import os
import json
import pickle
import numpy as np
from typing import Dict, List, Tuple

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml", "model")
MODEL_PATH = os.path.join(MODEL_DIR, "rf_model.pkl")
META_PATH  = os.path.join(MODEL_DIR, "model_meta.json")

_model = None
_explainer = None
_feature_cols: List[str] = []


def _load_model():
    global _model, _explainer, _feature_cols

    if _model is not None:
        return

    with open(MODEL_PATH, "rb") as f:
        _model = pickle.load(f)

    with open(META_PATH, "r") as f:
        meta = json.load(f)
    _feature_cols = meta["feature_cols"]

    # Set up SHAP explainer lazily (only if shap is available)
    try:
        import shap
        rf = _model.named_steps["rf"]
        _explainer = shap.TreeExplainer(rf)
        print("SHAP explainer loaded [OK]")
    except Exception as e:
        print(f"SHAP not available: {e}")
        _explainer = None


def get_feature_cols() -> List[str]:
    _load_model()
    return _feature_cols


def predict(features: Dict[str, float]) -> Tuple[float, str, str, Dict[str, float]]:
    """
    Run prediction for a single machine.

    Returns:
        (failure_probability, risk_level, recommended_action, explanation)
    """
    _load_model()

    # Build feature vector in correct order
    x = np.array([[features.get(f, 0.0) for f in _feature_cols]])

    prob = float(_model.predict_proba(x)[0][1])

    risk_level = (
        "critical" if prob >= 0.7
        else "at_risk" if prob >= 0.4
        else "healthy"
    )

    recommended_action = {
        "critical": "Schedule immediate maintenance inspection.",
        "at_risk":  "Monitor closely — maintenance recommended within 48 hours.",
        "healthy":  "No action required. Continue normal operation.",
    }[risk_level]

    # SHAP explanation
    explanation: Dict[str, float] = {}
    if _explainer is not None:
        try:
            scaler = _model.named_steps["scaler"]
            x_scaled = scaler.transform(x)
            shap_vals = _explainer.shap_values(x_scaled)
            # Take class-1 SHAP values
            sv = shap_vals[1][0] if isinstance(shap_vals, list) else shap_vals[0]
            full_explanation = {
                feat: round(float(val), 4)
                for feat, val in zip(_feature_cols, sv)
            }
            # Return top 5 by absolute value
            explanation = dict(
                sorted(full_explanation.items(), key=lambda kv: abs(kv[1]), reverse=True)[:5]
            )
        except Exception as e:
            print(f"SHAP inference error: {e}")

    if not explanation:
        # Fallback: use feature importances
        importances = _model.named_steps["rf"].feature_importances_
        imp_dict = {f: round(float(v), 4) for f, v in zip(_feature_cols, importances)}
        explanation = dict(
            sorted(imp_dict.items(), key=lambda kv: abs(kv[1]), reverse=True)[:5]
        )

    return prob, risk_level, recommended_action, explanation
