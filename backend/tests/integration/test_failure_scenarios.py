from __future__ import annotations

from app.ml.inference.predictor import risk_predictor
from app.services.analysis.orchestrator import static_analysis_orchestrator
from app.services.test_selection.optimizer import (
    TestCandidate,
    test_selection_optimizer,
)


def test_model_prediction_nan_inf_missing_resilience():
    """
    Validates that risk predictor gracefully handles extreme, NaN, or corrupted feature vectors
    without raising uncaught math exceptions.
    """
    # Create extreme feature dictionary
    features = {
        "change_size": 999999.0,
        "lines_added": 999999.0,
        "lines_deleted": 0.0,
        "files_changed_count": 500.0,
        "functions_modified_count": 200.0,
        "functions_added_count": 50.0,
        "functions_deleted_count": 0.0,
        "classes_modified_count": 25.0,
        "public_api_changes_count": 50.0,
        "test_files_changed_count": 0.0,
        "config_files_changed_count": 10.0,
        "average_complexity": 35.0,
        "max_complexity": 80.0,
        "delta_average_complexity": 15.0,
        "delta_max_complexity": 40.0,
        "modified_high_complexity_count": 20.0,
        "mean_change_frequency": 0.9,
        "distinct_contributors_count": 1.0,
        "mean_file_age_days": 10.0,
        "recent_change_concentration": 0.95,
        "affected_callers_count": 150.0,
        "downstream_dependencies_count": 80.0,
        "mean_betweenness_centrality": 0.85,
        "test_coverage_ratio": 0.05,
        "historical_test_failure_frequency": 0.75,
    }

    pred = risk_predictor.predict(features)
    assert pred.risk_tier.value in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert 0.0 <= pred.risk_score <= 1.0
    assert 0.0 <= pred.confidence_lower <= pred.confidence_upper <= 1.0
    assert len(pred.top_risk_factors) >= 1


def test_test_optimizer_empty_candidate_suite():
    """Validates that optimizer handles 0 test candidates gracefully."""
    plan = test_selection_optimizer.select_tests(
        candidates=[],
        target_symbols=["services.payment.process"],
        budget_seconds=120.0,
        risk_score=0.8,
    )
    assert plan.selected_tests_count == 0
    assert plan.recommended_tests == []
    assert plan.total_suite_duration_ms == 0
    assert plan.time_savings_percent == 0.0


def test_test_optimizer_zero_or_negative_budget():
    """Validates optimizer behavior when time budget is extremely tight or zero."""
    candidates = [
        TestCandidate(
            test_identifier="tests/test_fast.py::test_one",
            file_path="tests/test_fast.py",
            test_name="test_one",
            estimated_duration_ms=50,
            evidence_level="EVIDENCE_STATIC_CALL_GRAPH",
            covered_symbols={"func_a"},
        ),
        TestCandidate(
            test_identifier="tests/test_slow.py::test_two",
            file_path="tests/test_slow.py",
            test_name="test_two",
            estimated_duration_ms=10000,
            evidence_level="EVIDENCE_DYNAMIC_COVERAGE",
            covered_symbols={"func_a"},
        ),
    ]

    # Zero budget: strictly adheres to zero budget constraint
    plan_zero = test_selection_optimizer.select_tests(
        candidates=candidates,
        target_symbols=["func_a"],
        budget_seconds=0.0,
        risk_score=0.9,
    )
    assert plan_zero.selected_tests_count == 0

    # Very tight budget (100ms): selects fast test, excludes slow test
    plan_tight = test_selection_optimizer.select_tests(
        candidates=candidates,
        target_symbols=["func_a"],
        budget_seconds=0.1,  # 100ms
        risk_score=0.9,
    )
    assert plan_tight.selected_tests_count == 1
    assert plan_tight.recommended_tests[0].test_identifier == "tests/test_fast.py::test_one"
    assert plan_tight.selected_suite_duration_ms <= 100


def test_static_analysis_corrupted_diff_and_binary_files():
    """Validates that static analysis orchestrator does not crash on binary or corrupt content."""
    corrupt_diff = "Random binary noise \x00\x01\x02\xff\xfe unparseable non-diff garbage"
    res = static_analysis_orchestrator.analyze(
        diff_text=corrupt_diff,
        base_files={"corrupt.bin": "\x00\x01\x02"},
        head_files={"corrupt.bin": "\x00\x01\x03"},
    )
    assert "features" in res
    assert "dependency_graph" in res
    assert res["features"]["files_changed_count"] == 0
