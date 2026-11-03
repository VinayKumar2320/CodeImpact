from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.repository import Repository

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.get("", summary="List Registered Repositories")
async def list_repositories(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(Repository).offset(skip).limit(limit)
    result = await db.execute(stmt)
    repos = result.scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "github_id": r.github_id,
                "owner": r.owner,
                "name": r.name,
                "full_name": r.full_name,
                "default_branch": r.default_branch,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in repos
        ],
        "total": len(repos),
        "skip": skip,
        "limit": limit,
    }
