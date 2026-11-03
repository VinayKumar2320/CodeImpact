import httpx
import pytest

from app.ml.inference.predictor import FactorAttribution, RiskPredictionResult
from app.models.prediction import RiskTier
from app.services.reporting.check_runs import GitHubCheckRunPublisher
from app.services.test_selection.optimizer import TestRecommendationItem, TestSelectionPlan


@pytest.fixture
def sample_prediction():
    return RiskPredictionResult(
        risk_score=0.45,
        risk_tier=RiskTier.MEDIUM,
        confidence_lower=0.35,
        confidence_upper=0.55,
        model_version="1.0.0",
        model_name="xgboost",
        top_risk_factors=[
            FactorAttribution(
                feature_name="delta_average_complexity",
                feature_value=3.5,
                attribution_score=0.15,
                direction="RISK_INCREASING",
                human_explanation="Increased cyclomatic complexity (+3.5) elevated risk by +0.150.",
            )
        ],
        top_protective_factors=[
            FactorAttribution(
                feature_name="test_coverage_ratio",
                feature_value=0.92,
                attribution_score=-0.12,
                direction="RISK_REDUCING",
                human_explanation="High pre-merge test coverage (92%) mitigated risk by -0.120.",
            )
        ],
        raw_features={"change_size": 150.0},
    )


@pytest.fixture
def sample_test_plan():
    return TestSelectionPlan(
        recommended_tests=[
            TestRecommendationItem(
                rank=1,
                test_identifier="tests/test_auth.py::test_login",
                file_path="tests/test_auth.py",
                test_name="test_login",
                selection_reason="Direct dynamic coverage",
                evidence_level="EVIDENCE_DYNAMIC_COVERAGE",
                estimated_duration_ms=400,
                priority_score=15.2,
                covered_symbols=["app/auth.py:login"],
            )
        ],
        total_suite_tests_count=20,
        selected_tests_count=1,
        total_suite_duration_ms=10000,
        selected_suite_duration_ms=400,
        time_savings_percent=96.0,
        test_reduction_percent=95.0,
        budget_limit_ms=60000,
        budget_consumed_ms=400,
    )


def test_format_check_run_payload(sample_prediction, sample_test_plan):
    publisher = GitHubCheckRunPublisher()
    static_result = {
        "diff": {"files": [{"new_path": "app/auth.py"}]},
        "dependencies": {"affected_callers_count": 2, "mean_betweenness_centrality": 0.05},
    }

    payload = publisher.format_check_run_payload(
        prediction=sample_prediction,
        test_plan=sample_test_plan,
        static_result=static_result,
        head_sha="head1234567890",
    )

    assert payload["head_sha"] == "head1234567890"
    assert payload["status"] == "completed"
    assert payload["conclusion"] == "neutral"  # Informational check
    assert "Risk: MEDIUM (45%)" in payload["output"]["title"]
    assert "pytest tests/test_auth.py::test_login" in payload["output"]["text"]
    assert "<details>" in payload["output"]["text"]


async def test_publish_local_mock_mode(sample_prediction, sample_test_plan):
    publisher = GitHubCheckRunPublisher()
    payload = publisher.format_check_run_payload(
        prediction=sample_prediction,
        test_plan=sample_test_plan,
        static_result={},
        head_sha="head1234",
    )

    result = await publisher.publish(
        repo_full_name="tiangolo/fastapi",
        commit_sha="head1234",
        payload=payload,
        installation_token=None,  # Local mode
    )

    assert result["status"] == "published_locally"
    assert result["payload"] == payload


async def test_publish_remote_github_success(sample_prediction, sample_test_plan):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test_token"
        assert request.url.path == "/repos/tiangolo/fastapi/check-runs"
        return httpx.Response(201, json={"id": 9999, "status": "completed"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        publisher = GitHubCheckRunPublisher(http_client=mock_client)
        payload = publisher.format_check_run_payload(
            prediction=sample_prediction,
            test_plan=sample_test_plan,
            static_result={},
            head_sha="head1234",
        )

        res = await publisher.publish(
            repo_full_name="tiangolo/fastapi",
            commit_sha="head1234",
            payload=payload,
            installation_token="test_token",
        )

        assert res["id"] == 9999
