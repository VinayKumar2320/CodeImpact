from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.pull_request import PullRequest

router = APIRouter(prefix="/pull-requests", tags=["Pull Requests"])


@router.get("", summary="List Pull Requests")
async def list_pull_requests(
    repository_id: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(PullRequest)
    if repository_id:
        stmt = stmt.where(PullRequest.repository_id == repository_id)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    prs = result.scalars().all()
    return {
        "items": [
            {
                "id": p.id,
                "repository_id": p.repository_id,
                "pr_number": p.pr_number,
                "title": p.title,
                "state": p.state,
                "author": p.author,
                "head_sha": p.head_sha,
                "base_sha": p.base_sha,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in prs
        ],
        "total": len(prs),
    }
