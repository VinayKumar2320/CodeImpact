import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.analysis import Analysis
from app.models.model_version import ModelVersion
from app.models.prediction import Prediction
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.test_case import TestCase, TestRecommendation


@pytest.mark.asyncio
async def test_repository_and_pull_request_creation(db_session: AsyncSession):
    repo = Repository(
        github_id=987654321,
        owner="fastapi",
        name="fastapi",
        full_name="fastapi/fastapi",
        default_branch="master",
    )
    db_session.add(repo)
    await db_session.flush()

    assert repo.id is not None

    pr = PullRequest(
        repository_id=repo.id,
        github_pr_id=12345,
        pr_number=42,
        title="Add background task cancellation",
        author="tiangolo",
        base_sha="a" * 40,
        head_sha="b" * 40,
        head_ref="feature/cancel-task",
    )
    db_session.add(pr)
    await db_session.flush()

    assert pr.id is not None
    assert pr.repository_id == repo.id

    # Add analysis
    analysis = Analysis(
        pull_request_id=pr.id,
        commit_sha=pr.head_sha,
        base_sha=pr.base_sha,
        status="COMPLETED",
        features={"lines_added": 120, "cyclomatic_complexity": 8},
        execution_duration_ms=1450,
    )
    db_session.add(analysis)
    await db_session.flush()

    # Add model version & prediction
    model_version = ModelVersion(
        name="xgboost_risk_classifier",
        version="v1.0.0",
        algorithm="xgboost",
        pr_auc=0.84,
        roc_auc=0.89,
        is_active=True,
    )
    db_session.add(model_version)
    await db_session.flush()

    pred = Prediction(
        analysis_id=analysis.id,
        model_version_id=model_version.id,
        risk_score=0.78,
        risk_tier="HIGH",
        calibrated_probability=0.74,
        feature_attributions={"cyclomatic_complexity": 0.35, "lines_added": 0.22},
        confidence=0.95,
    )
    db_session.add(pred)

    # Add test cases and recommendation
    test_case = TestCase(
        repository_id=repo.id,
        test_identifier="tests/test_background.py::test_cancel",
        file_path="tests/test_background.py",
        test_name="test_cancel",
        average_duration_ms=320,
    )
    db_session.add(test_case)
    await db_session.flush()

    rec = TestRecommendation(
        analysis_id=analysis.id,
        test_case_id=test_case.id,
        test_identifier=test_case.test_identifier,
        rank=1,
        selection_reason="Directly exercises modified background cancellation routine",
        evidence_level="EVIDENCE_DYNAMIC_COVERAGE",
        priority_score=0.92,
    )
    db_session.add(rec)
    await db_session.commit()

    # Query back
    stmt = (
        select(Analysis)
        .options(selectinload(Analysis.prediction), selectinload(Analysis.recommended_tests))
        .where(Analysis.id == analysis.id)
    )
    res = await db_session.execute(stmt)
    saved_analysis = res.scalar_one()

    assert saved_analysis.status == "COMPLETED"
    assert saved_analysis.features["cyclomatic_complexity"] == 8
    assert saved_analysis.prediction is not None
    assert saved_analysis.prediction.risk_tier == "HIGH"
    assert len(saved_analysis.recommended_tests) == 1
    assert saved_analysis.recommended_tests[0].rank == 1
