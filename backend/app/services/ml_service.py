"""
ML service — loads the trained sklearn Random Forest and runs inference + SHAP.
Model is loaded once at startup and cached for the lifetime of the server.

Two inference modes:
  predict_fast(features) — just sklearn predict_proba, <5ms, used by the simulator
  predict(features)      — full inference with SHAP explanation, ~2s, used by the API
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


def _build_vector(features: Dict[str, float]) -> np.ndarray:
    return np.array([[features.get(f, 0.0) for f in _feature_cols]])


def _classify(prob: float) -> Tuple[str, str]:
    """Map probability → (risk_level, recommended_action)."""
    if prob >= 0.7:
        return "critical", "Schedule immediate maintenance inspection."
    elif prob >= 0.4:
        return "at_risk", "Monitor closely — maintenance recommended within 48 hours."
    else:
        return "healthy", "No action required. Continue normal operation."


def predict_fast(features: Dict[str, float]) -> Tuple[float, str, str]:
    """
    Fast inference — no SHAP. Used by the background simulator loop.
    ~5ms per call (vs ~2000ms with SHAP).

    Returns: (failure_probability, risk_level, recommended_action)
    """
    _load_model()
    x = _build_vector(features)
    prob = float(_model.predict_proba(x)[0][1])
    risk_level, action = _classify(prob)
    return prob, risk_level, action


def predict(features: Dict[str, float]) -> Tuple[float, str, str, Dict[str, float]]:
    """
    Full inference with SHAP explanation. Used by the prediction API endpoint.
    ~2s per call due to SHAP tree computation.

    Returns: (failure_probability, risk_level, recommended_action, explanation)
    """
    _load_model()

    x = _build_vector(features)
    prob = float(_model.predict_proba(x)[0][1])
    risk_level, action = _classify(prob)

    # SHAP explanation
    explanation: Dict[str, float] = {}
    if _explainer is not None:
        try:
            scaler = _model.named_steps["scaler"]
            x_scaled = scaler.transform(x)
            shap_vals = _explainer.shap_values(x_scaled)

            # Robustly handle all shap_values output formats:
            #   list of 2 arrays  -> [class0_arr, class1_arr]  (old shap / binary RF)
            #   list of 1 array   -> [combined_arr]            (newer shap binary)
            #   3-D ndarray       -> (n_classes, n_samples, n_feats)
            #   2-D ndarray       -> (n_samples, n_feats)
            if isinstance(shap_vals, list):
                if len(shap_vals) >= 2:
                    sv = np.asarray(shap_vals[1]).flatten()
                else:
                    sv = np.asarray(shap_vals[0]).flatten()
            elif isinstance(shap_vals, np.ndarray) and shap_vals.ndim == 3:
                sv = shap_vals[-1, 0, :]
            else:
                sv = np.asarray(shap_vals).flatten()

            full_explanation = {
                feat: round(float(val), 4)
                for feat, val in zip(_feature_cols, sv)
            }
            # Return top 8 by absolute SHAP value
            explanation = dict(
                sorted(full_explanation.items(), key=lambda kv: abs(kv[1]), reverse=True)[:8]
            )
        except Exception as e:
            print(f"SHAP inference error: {e}")

    if not explanation:
        # Fallback: use feature importances (always available, no SHAP needed)
        importances = _model.named_steps["rf"].feature_importances_
        imp_dict = {f: round(float(v), 4) for f, v in zip(_feature_cols, importances)}
        explanation = dict(
            sorted(imp_dict.items(), key=lambda kv: abs(kv[1]), reverse=True)[:8]
        )

    return prob, risk_level, action, explanation
