from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.analysis import Analysis

router = APIRouter(prefix="/analyses", tags=["Analyses"])


@router.get("/{analysis_id}", summary="Get Analysis Details")
async def get_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(Analysis).where(Analysis.id == analysis_id)
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis record not found")
    return {
        "id": analysis.id,
        "pull_request_id": analysis.pull_request_id,
        "commit_sha": analysis.commit_sha,
        "status": analysis.status,
        "analysis_version": analysis.analysis_version,
        "features": analysis.features,
        "execution_duration_ms": analysis.execution_duration_ms,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
    }
