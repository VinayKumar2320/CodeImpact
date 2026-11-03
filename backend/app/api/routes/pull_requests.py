from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.analysis import Analysis, AnalysisStatus
from app.models.pull_request import PullRequest
from app.schemas.pull_request import PullRequestResponse

router = APIRouter(prefix="/pull-requests", tags=["Pull Requests"])


@router.get("", response_model=list[PullRequestResponse], summary="List pull requests")
async def list_pull_requests(
    repository_id: str | None = Query(None, description="Filter by repository ID"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[PullRequestResponse]:
    stmt = (
        select(PullRequest)
        .options(
            selectinload(PullRequest.analyses).selectinload(Analysis.prediction),
        )
        .order_by(desc(PullRequest.updated_at))
        .limit(limit)
    )

    if repository_id:
        stmt = stmt.where(PullRequest.repository_id == repository_id)

    result = await db.execute(stmt)
    prs = result.scalars().all()

    responses: list[PullRequestResponse] = []
    for pr in prs:
        latest_analysis = None
        if pr.analyses:
            sorted_analyses = sorted(pr.analyses, key=lambda a: a.created_at, reverse=True)
            latest_analysis = sorted_analyses[0]

        latest_id = latest_analysis.id if latest_analysis else None
        latest_tier = (
            latest_analysis.prediction.risk_tier
            if latest_analysis and latest_analysis.prediction
            else None
        )
        latest_score = (
            latest_analysis.prediction.risk_score
            if latest_analysis and latest_analysis.prediction
            else None
        )

        responses.append(
            PullRequestResponse(
                id=pr.id,
                repository_id=pr.repository_id,
                pr_number=pr.pr_number,
                title=pr.title,
                author=pr.author,
                base_ref=pr.base_ref,
                head_ref=pr.head_ref,
                base_sha=pr.base_sha,
                head_sha=pr.head_sha,
                state=pr.state,
                created_at=pr.created_at,
                updated_at=pr.updated_at,
                latest_analysis_id=latest_id,
                latest_risk_tier=latest_tier,
                latest_risk_score=latest_score,
            )
        )

    return responses


@router.get(
    "/{pull_request_id}", response_model=PullRequestResponse, summary="Get pull request details"
)
async def get_pull_request(
    pull_request_id: str,
    db: AsyncSession = Depends(get_db),
) -> PullRequestResponse:
    stmt = (
        select(PullRequest)
        .options(
            selectinload(PullRequest.analyses).selectinload(Analysis.prediction),
        )
        .where(PullRequest.id == pull_request_id)
    )
    pr = (await db.execute(stmt)).scalar_one_or_none()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")

    latest_analysis = None
    if pr.analyses:
        sorted_analyses = sorted(pr.analyses, key=lambda a: a.created_at, reverse=True)
        latest_analysis = sorted_analyses[0]

    return PullRequestResponse(
        id=pr.id,
        repository_id=pr.repository_id,
        pr_number=pr.pr_number,
        title=pr.title,
        author=pr.author,
        base_ref=pr.base_ref,
        head_ref=pr.head_ref,
        base_sha=pr.base_sha,
        head_sha=pr.head_sha,
        state=pr.state,
        created_at=pr.created_at,
        updated_at=pr.updated_at,
        latest_analysis_id=latest_analysis.id if latest_analysis else None,
        latest_risk_tier=latest_analysis.prediction.risk_tier
        if latest_analysis and latest_analysis.prediction
        else None,
        latest_risk_score=latest_analysis.prediction.risk_score
        if latest_analysis and latest_analysis.prediction
        else None,
    )


@router.post("/{pull_request_id}/analyze", summary="Trigger manual analysis for pull request")
async def trigger_analysis(
    pull_request_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(PullRequest).where(PullRequest.id == pull_request_id)
    pr = (await db.execute(stmt)).scalar_one_or_none()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")

    analysis_id = str(uuid.uuid4())
    analysis = Analysis(
        id=analysis_id,
        pull_request_id=pr.id,
        commit_sha=pr.head_sha,
        base_sha=pr.base_sha,
        status=AnalysisStatus.QUEUED.value,
        analysis_version="1.0.0",
    )
    db.add(analysis)
    await db.commit()

    return {
        "analysis_id": analysis.id,
        "status": analysis.status,
        "message": f"Queued analysis for PR #{pr.pr_number} ({pr.head_sha[:7]})",
    }
