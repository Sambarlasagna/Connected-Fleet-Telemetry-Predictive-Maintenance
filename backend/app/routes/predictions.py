from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from fastapi import Depends
from app.database.connection import get_db
from app.models.schemas import PredictionResponse
from sqlalchemy import text
import json

router = APIRouter()


@router.get("/vehicles/{machine_id}/prediction", response_model=PredictionResponse)
def get_prediction(machine_id: int, db: Session = Depends(get_db)):
    """Current failure prediction and SHAP explanation for a machine."""
    row = db.execute(text("""
        SELECT machine_id, failure_probability, risk_level, recommended_action, explanation
        FROM predictions
        WHERE machine_id = :mid
    """), {"mid": machine_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Prediction not found")

    explanation = row.explanation
    if isinstance(explanation, str):
        explanation = json.loads(explanation)

    return PredictionResponse(
        machine_id=row.machine_id,
        failure_probability=row.failure_probability,
        risk_level=row.risk_level,
        recommended_action=row.recommended_action,
        explanation=explanation,
    )
