from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.services.test_selection.coverage_mapper import TestCandidate

logger = get_logger(__name__)

EVIDENCE_WEIGHTS: dict[str, float] = {
    "EVIDENCE_DYNAMIC_COVERAGE": 1.0,
    "EVIDENCE_STATIC_CALL_GRAPH": 0.8,
    "EVIDENCE_DEPENDENCY_HEURISTIC": 0.5,
}


@dataclass
class TestRecommendationItem:
    __test__ = False
    rank: int
    test_identifier: str
    file_path: str
    test_name: str
    selection_reason: str
    evidence_level: str
    estimated_duration_ms: int
    priority_score: float
    covered_symbols: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "test_identifier": self.test_identifier,
            "file_path": self.file_path,
            "test_name": self.test_name,
            "selection_reason": self.selection_reason,
            "evidence_level": self.evidence_level,
            "estimated_duration_ms": self.estimated_duration_ms,
            "priority_score": round(self.priority_score, 4),
            "covered_symbols": self.covered_symbols,
        }


@dataclass
class TestSelectionPlan:
    __test__ = False
    recommended_tests: list[TestRecommendationItem]
    total_suite_tests_count: int
    selected_tests_count: int
    total_suite_duration_ms: int
    selected_suite_duration_ms: int
    time_savings_percent: float
    test_reduction_percent: float
    budget_limit_ms: int
    budget_consumed_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommended_tests": [t.to_dict() for t in self.recommended_tests],
            "total_suite_tests_count": self.total_suite_tests_count,
            "selected_tests_count": self.selected_tests_count,
            "total_suite_duration_ms": self.total_suite_duration_ms,
            "selected_suite_duration_ms": self.selected_suite_duration_ms,
            "time_savings_percent": round(self.time_savings_percent, 2),
            "test_reduction_percent": round(self.test_reduction_percent, 2),
            "budget_limit_ms": self.budget_limit_ms,
            "budget_consumed_ms": self.budget_consumed_ms,
        }


class TestSelectionOptimizer:
    """
    Intelligent Budgeted Test Selection Optimizer.
    Maximizes marginal coverage of modified symbols and defect-prone code paths
    under strict execution time constraints.
    """

    def select_tests(
        self,
        candidates: list[TestCandidate],
        target_symbols: list[str],
        budget_seconds: float = 60.0,
        risk_score: float = 0.5,
    ) -> TestSelectionPlan:
        """
        Executes greedy marginal coverage optimization under budget constraint B.
        """
        if not candidates:
            return TestSelectionPlan(
                recommended_tests=[],
                total_suite_tests_count=0,
                selected_tests_count=0,
                total_suite_duration_ms=0,
                selected_suite_duration_ms=0,
                time_savings_percent=0.0,
                test_reduction_percent=0.0,
                budget_limit_ms=int(budget_seconds * 1000),
                budget_consumed_ms=0,
            )

        total_suite_count = len(candidates)
        total_suite_duration = sum(c.estimated_duration_ms for c in candidates)
        budget_limit_ms = int(budget_seconds * 1000)

        uncovered_targets = set(target_symbols)
        selected: list[TestRecommendationItem] = []
        remaining_candidates = list(candidates)
        current_time_ms = 0

        # Iteratively pick test with highest marginal utility per unit time
        while remaining_candidates and current_time_ms < budget_limit_ms:
            best_candidate: TestCandidate | None = None
            best_score = -1.0
            best_marginal_symbols: list[str] = []

            for cand in remaining_candidates:
                # Check if adding test exceeds budget
                if current_time_ms + cand.estimated_duration_ms > budget_limit_ms and selected:
                    continue

                evidence_w = EVIDENCE_WEIGHTS.get(cand.evidence_level, 0.5)
                # Overlap with target symbols and marginal new targets
                target_overlap = len(cand.covered_symbols.intersection(set(target_symbols)))
                marginal_cov = cand.covered_symbols.intersection(uncovered_targets)
                marginal_gain = len(marginal_cov)

                # Failure history bonus
                failure_bonus = 1.0 + (cand.historical_failure_rate * 3.0)

                # Duration normalization
                duration_sec = max(0.1, cand.estimated_duration_ms / 1000.0)
                time_cost = math.log1p(duration_sec) + 0.1

                # Prioritize tests touching modified symbols above all else
                relevance_multiplier = 5.0 if target_overlap > 0 else 0.2

                # Composite marginal priority formula
                score = (
                    (
                        (evidence_w * 3.0)
                        + (target_overlap * 4.0)
                        + (marginal_gain * (3.0 + risk_score * 3.0))
                        + (failure_bonus * 1.5)
                    )
                    * relevance_multiplier
                    / time_cost
                )

                if score > best_score:
                    best_score = score
                    best_candidate = cand
                    best_marginal_symbols = sorted(cand.covered_symbols)

            if best_candidate is None:
                break

            current_time_ms += best_candidate.estimated_duration_ms
            uncovered_targets.difference_update(best_candidate.covered_symbols)
            remaining_candidates.remove(best_candidate)

            rank = len(selected) + 1
            selected.append(
                TestRecommendationItem(
                    rank=rank,
                    test_identifier=best_candidate.test_identifier,
                    file_path=best_candidate.file_path,
                    test_name=best_candidate.test_name,
                    selection_reason=best_candidate.selection_reason,
                    evidence_level=best_candidate.evidence_level,
                    estimated_duration_ms=best_candidate.estimated_duration_ms,
                    priority_score=best_score,
                    covered_symbols=best_marginal_symbols,
                )
            )

        selected_duration = current_time_ms
        time_savings = (
            ((total_suite_duration - selected_duration) / max(total_suite_duration, 1)) * 100.0
            if total_suite_duration > 0
            else 0.0
        )
        test_reduction = (
            ((total_suite_count - len(selected)) / max(total_suite_count, 1)) * 100.0
            if total_suite_count > 0
            else 0.0
        )

        return TestSelectionPlan(
            recommended_tests=selected,
            total_suite_tests_count=total_suite_count,
            selected_tests_count=len(selected),
            total_suite_duration_ms=total_suite_duration,
            selected_suite_duration_ms=selected_duration,
            time_savings_percent=max(0.0, time_savings),
            test_reduction_percent=max(0.0, test_reduction),
            budget_limit_ms=budget_limit_ms,
            budget_consumed_ms=selected_duration,
        )


test_selection_optimizer = TestSelectionOptimizer()
