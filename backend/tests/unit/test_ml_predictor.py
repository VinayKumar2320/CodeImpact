from pathlib import Path

from app.ml.inference.predictor import RiskPredictor
from app.models.prediction import RiskTier


def test_predictor_loads_trained_model():
    model_path = (
        Path(__file__).resolve().parents[2] / "app" / "ml" / "models_store" / "risk_model_v1.joblib"
    )
    predictor = RiskPredictor(model_path=model_path if model_path.exists() else None)

    assert predictor.model_name in ("xgboost", "heuristic_fallback")
    assert predictor.model_version is not None


def test_predictor_inference_low_vs_high_risk():
    predictor = RiskPredictor()

    low_risk_features = {
        "change_size": 15,
        "lines_added": 10,
        "lines_deleted": 5,
        "files_changed_count": 1,
        "functions_modified_count": 1,
        "delta_average_complexity": 0.0,
        "modified_high_complexity_count": 0,
        "affected_callers_count": 0,
        "public_api_changes_count": 0,
        "test_coverage_ratio": 0.98,
        "mean_change_frequency": 0.5,
    }

    high_risk_features = {
        "change_size": 2500,
        "lines_added": 1800,
        "lines_deleted": 700,
        "files_changed_count": 25,
        "functions_modified_count": 18,
        "classes_modified_count": 5,
        "public_api_changes_count": 8,
        "average_complexity": 8.0,
        "max_complexity": 22,
        "delta_average_complexity": 6.5,
        "delta_max_complexity": 12,
        "modified_high_complexity_count": 8,
        "mean_change_frequency": 14.0,
        "distinct_contributors_count": 10,
        "mean_file_age_days": 15.0,
        "affected_callers_count": 35,
        "downstream_dependencies_count": 40,
        "test_coverage_ratio": 0.15,
        "historical_test_failure_frequency": 0.45,
    }

    low_res = predictor.predict(low_risk_features)
    high_res = predictor.predict(high_risk_features)

    assert 0.0 <= low_res.risk_score <= 1.0
    assert 0.0 <= high_res.risk_score <= 1.0
    assert low_res.risk_tier in (RiskTier.LOW, RiskTier.MEDIUM, RiskTier.HIGH, RiskTier.CRITICAL)
    assert high_res.risk_tier in (RiskTier.LOW, RiskTier.MEDIUM, RiskTier.HIGH, RiskTier.CRITICAL)

    # Check that attributions contain human explanations
    all_factors = high_res.top_risk_factors + high_res.top_protective_factors
    assert len(all_factors) > 0
    for f in all_factors:
        assert len(f.human_explanation) > 10
        assert f.direction in ("RISK_INCREASING", "RISK_REDUCING")


def test_predictor_fallback_when_model_missing():
    predictor = RiskPredictor(model_path="/nonexistent/model.joblib")
    features = {
        "change_size": 100,
        "delta_average_complexity": 1.0,
        "affected_callers_count": 2,
    }
    result = predictor.predict(features)
    assert 0.0 <= result.risk_score <= 1.0
    assert result.model_name == "heuristic_fallback"
    assert result.model_version == "0.9.0-heuristic"
