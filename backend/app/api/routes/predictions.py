from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.prediction import Prediction

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.get("/{prediction_id}", summary="Get Risk Prediction Details")
async def get_prediction(
    prediction_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(Prediction).where(Prediction.id == prediction_id)
    result = await db.execute(stmt)
    pred = result.scalar_one_or_none()
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction record not found")
    return {
        "id": pred.id,
        "analysis_id": pred.analysis_id,
        "risk_score": pred.risk_score,
        "risk_tier": pred.risk_tier,
        "calibrated_probability": pred.calibrated_probability,
        "feature_attributions": pred.feature_attributions,
        "confidence": pred.confidence,
        "is_experimental": pred.is_experimental,
    }
