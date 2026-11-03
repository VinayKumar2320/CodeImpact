from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.analysis import Analysis, AnalysisStatus
from app.models.prediction import Prediction
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.schemas.metrics import PlatformMetricsResponse

router = APIRouter(prefix="/metrics", tags=["Metrics"])

# Prometheus Metrics
ANALYSES_TOTAL = Counter(
    "codeimpact_analyses_total", "Total pull request analyses executed", ["status"]
)
RISK_SCORE_HISTOGRAM = Histogram(
    "codeimpact_risk_score",
    "Distribution of predicted regression risk scores",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)
TEST_TIME_SAVED_SECONDS = Counter(
    "codeimpact_test_time_saved_seconds_total", "Cumulative test execution seconds saved"
)


@router.get("", response_model=PlatformMetricsResponse, summary="Get Platform Summary Analytics")
async def get_platform_metrics(
    db: AsyncSession = Depends(get_db),
) -> PlatformMetricsResponse:
    # 1. Total counts
    repo_count = (await db.execute(select(func.count(Repository.id)))).scalar_one() or 0
    pr_count = (await db.execute(select(func.count(PullRequest.id)))).scalar_one() or 0
    total_analyses = (await db.execute(select(func.count(Analysis.id)))).scalar_one() or 0
    completed_analyses = (
        await db.execute(
            select(func.count(Analysis.id)).where(Analysis.status == AnalysisStatus.COMPLETED.value)
        )
    ).scalar_one() or 0

    # 2. Risk Metrics
    avg_risk = (await db.execute(select(func.avg(Prediction.risk_score)))).scalar_one() or 0.0

    # 3. Risk Tier Distribution
    tier_rows = (
        await db.execute(
            select(Prediction.risk_tier, func.count(Prediction.id)).group_by(Prediction.risk_tier)
        )
    ).all()
    tier_dist = dict(tier_rows)
    # Ensure all tiers are present
    for t in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        tier_dist.setdefault(t, 0)

    # 4. Total test time savings estimation
    time_saved_hours = completed_analyses * 0.45

    return PlatformMetricsResponse(
        total_repositories=repo_count,
        total_pull_requests=pr_count,
        total_analyses=total_analyses,
        completed_analyses=completed_analyses,
        average_risk_score=round(float(avg_risk), 4),
        risk_tier_distribution=tier_dist,
        total_test_time_saved_hours=round(time_saved_hours, 2),
        average_test_time_savings_percent=72.5,
        active_model_name="xgboost",
        active_model_version="1.0.0",
    )


@router.get("/prometheus", summary="Prometheus Application Metrics")
async def get_prometheus_metrics() -> Response:
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
