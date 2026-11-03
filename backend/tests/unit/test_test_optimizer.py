from app.services.test_selection.coverage_mapper import TestCandidate
from app.services.test_selection.optimizer import TestSelectionOptimizer


def test_optimizer_selects_under_budget():
    optimizer = TestSelectionOptimizer()
    candidates = [
        TestCandidate(
            test_identifier=f"test_{i}",
            file_path=f"test_{i}.py",
            test_name=f"test_{i}",
            estimated_duration_ms=1000,
            covered_symbols={f"sym_{i}"},
        )
        for i in range(20)
    ]

    # 5.0 seconds budget = 5000ms
    plan = optimizer.select_tests(
        candidates=candidates,
        target_symbols=["sym_1", "sym_2"],
        budget_seconds=5.0,
        risk_score=0.8,
    )

    assert plan.budget_consumed_ms <= plan.budget_limit_ms
    assert len(plan.recommended_tests) <= 5
    assert plan.time_savings_percent >= 50.0
    assert plan.test_reduction_percent >= 50.0


def test_optimizer_prioritizes_dynamic_coverage_and_risk():
    optimizer = TestSelectionOptimizer()
    cand1 = TestCandidate(
        test_identifier="test_dynamic",
        file_path="tests/test_auth.py",
        test_name="test_dynamic",
        estimated_duration_ms=500,
        covered_symbols={"auth.login"},
        evidence_level="EVIDENCE_DYNAMIC_COVERAGE",
        selection_reason="Direct dynamic coverage",
    )
    cand2 = TestCandidate(
        test_identifier="test_heuristic",
        file_path="tests/test_misc.py",
        test_name="test_heuristic",
        estimated_duration_ms=500,
        covered_symbols=set(),
        evidence_level="EVIDENCE_DEPENDENCY_HEURISTIC",
        selection_reason="Heuristic",
    )

    plan = optimizer.select_tests(
        candidates=[cand2, cand1],
        target_symbols=["auth.login"],
        budget_seconds=10.0,
        risk_score=0.7,
    )

    assert len(plan.recommended_tests) == 2
    assert plan.recommended_tests[0].test_identifier == "test_dynamic"
    assert plan.recommended_tests[0].rank == 1


def test_optimizer_handles_empty_candidates():
    optimizer = TestSelectionOptimizer()
    plan = optimizer.select_tests(
        candidates=[],
        target_symbols=["sym_1"],
        budget_seconds=30.0,
    )
    assert len(plan.recommended_tests) == 0
    assert plan.selected_tests_count == 0
