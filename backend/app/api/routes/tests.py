from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.test_case import TestCase

router = APIRouter(prefix="/tests", tags=["Test Cases"])


@router.get("", summary="List Test Cases")
async def list_tests(
    repository_id: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(TestCase)
    if repository_id:
        stmt = stmt.where(TestCase.repository_id == repository_id)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    tests = result.scalars().all()
    return {
        "items": [
            {
                "id": t.id,
                "repository_id": t.repository_id,
                "test_identifier": t.test_identifier,
                "file_path": t.file_path,
                "test_name": t.test_name,
                "average_duration_ms": t.average_duration_ms,
                "historical_failure_rate": t.historical_failure_rate,
            }
            for t in tests
        ],
        "total": len(tests),
    }
