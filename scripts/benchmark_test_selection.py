#!/usr/bin/env python3
"""
scripts/benchmark_test_selection.py
Empirical evaluation benchmarking 5 test selection strategies:
1. Full Suite
2. Random Sampling (under budget B)
3. Filename Matching Heuristic (under budget B)
4. Static Dependency Selection (under budget B)
5. CodeImpact Marginal Coverage Optimizer (under budget B)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.core.logging import get_logger
from app.services.test_selection.coverage_mapper import TestCandidate
from app.services.test_selection.optimizer import TestSelectionOptimizer

logger = get_logger("scripts.benchmark_test_selection")


def generate_synthetic_suite(num_tests: int = 150) -> list[TestCandidate]:
    """Generates realistic synthetic test suite with heterogeneous durations and coverages."""
    candidates = []
    modules = [
        "auth",
        "payments",
        "users",
        "api",
        "database",
        "orders",
        "cache",
        "notifications",
        "analytics",
        "search",
    ]

    for i in range(num_tests):
        mod = modules[i % len(modules)]
        is_integration = i % 5 == 0
        duration_ms = (
            random.randint(1200, 4500) if is_integration else random.randint(80, 500)
        )
        failure_rate = random.choice([0.01, 0.02, 0.05, 0.12, 0.25])

        # Symbol coverage
        num_symbols = random.randint(1, 4)
        covered = {
            f"{mod}.service::fn_{mod}_{random.randint(1, 10)}"
            for _ in range(num_symbols)
        }

        candidates.append(
            TestCandidate(
                test_identifier=f"tests/{mod}/test_{mod}_{i}.py::test_case_{i}",
                file_path=f"tests/{mod}/test_{mod}_{i}.py",
                test_name=f"test_case_{i}",
                estimated_duration_ms=duration_ms,
                historical_failure_rate=failure_rate,
                covered_symbols=covered,
                evidence_level="EVIDENCE_DEPENDENCY_HEURISTIC",
            )
        )

    return candidates


def run_benchmark(budget_seconds: float = 30.0, seed: int = 42) -> dict:
    random.seed(seed)
    suite = generate_synthetic_suite(150)
    budget_ms = int(budget_seconds * 1000)

    # Simulate PR: modifies symbols in 'auth' and 'payments'
    modified_targets = [
        "auth.service::fn_auth_1",
        "auth.service::fn_auth_2",
        "payments.service::fn_payments_3",
    ]

    # Tag truly failing/affected tests (ground truth regression detection)
    failing_tests = set()
    for test in suite:
        if (
            any(sym in test.covered_symbols for sym in modified_targets)
            and random.random() < 0.40
        ):
            failing_tests.add(test.test_identifier)

    if not failing_tests:
        # Guarantee at least 3 failing tests for reproducible evaluation
        for test in suite:
            if any(sym in test.covered_symbols for sym in modified_targets):
                failing_tests.add(test.test_identifier)
                if len(failing_tests) >= 3:
                    break

    logger.info(
        f"Generated test suite with {len(suite)} tests. Ground truth regressions: {len(failing_tests)}"
    )

    total_duration_ms = sum(t.estimated_duration_ms for t in suite)

    # 1. Strategy: Full Suite
    full_selected = [t.test_identifier for t in suite]
    full_duration = total_duration_ms
    full_caught = len(failing_tests.intersection(full_selected))

    # 2. Strategy: Random Sampling under Budget B
    random_candidates = list(suite)
    random.shuffle(random_candidates)
    random_selected = []
    random_time = 0
    for t in random_candidates:
        if random_time + t.estimated_duration_ms <= budget_ms:
            random_selected.append(t.test_identifier)
            random_time += t.estimated_duration_ms
    random_caught = len(failing_tests.intersection(random_selected))

    # 3. Strategy: Filename Matching under Budget B
    match_candidates = [
        t for t in suite if "auth" in t.file_path or "payments" in t.file_path
    ]
    filename_selected = []
    filename_time = 0
    for t in match_candidates:
        if filename_time + t.estimated_duration_ms <= budget_ms:
            filename_selected.append(t.test_identifier)
            filename_time += t.estimated_duration_ms
    filename_caught = len(failing_tests.intersection(filename_selected))

    # 4. Strategy: Static Dependency Selection under Budget B
    dep_candidates = [
        t for t in suite if any(sym in t.covered_symbols for sym in modified_targets)
    ]
    dep_selected = []
    dep_time = 0
    for t in dep_candidates:
        if dep_time + t.estimated_duration_ms <= budget_ms:
            dep_selected.append(t.test_identifier)
            dep_time += t.estimated_duration_ms
    dep_caught = len(failing_tests.intersection(dep_selected))

    # 5. Strategy: CodeImpact Marginal Coverage Optimizer
    # Mark evidence levels
    for t in suite:
        if any(sym in t.covered_symbols for sym in modified_targets):
            t.evidence_level = (
                "EVIDENCE_DYNAMIC_COVERAGE"
                if random.random() < 0.5
                else "EVIDENCE_STATIC_CALL_GRAPH"
            )
            t.selection_reason = "Covers modified symbol"
        else:
            t.evidence_level = "EVIDENCE_DEPENDENCY_HEURISTIC"

    optimizer = TestSelectionOptimizer()
    plan = optimizer.select_tests(
        candidates=suite,
        target_symbols=modified_targets,
        budget_seconds=budget_seconds,
        risk_score=0.72,
    )
    codeimpact_selected = [t.test_identifier for t in plan.recommended_tests]
    codeimpact_time = plan.selected_suite_duration_ms
    codeimpact_caught = len(failing_tests.intersection(codeimpact_selected))

    total_failing = len(failing_tests)

    results = {
        "budget_seconds": budget_seconds,
        "total_suite_size": len(suite),
        "total_suite_duration_sec": round(total_duration_ms / 1000.0, 2),
        "ground_truth_failing_tests_count": total_failing,
        "strategies": {
            "full_suite": {
                "name": "Full Test Suite",
                "tests_selected": len(full_selected),
                "duration_seconds": round(full_duration / 1000.0, 2),
                "time_savings_percent": 0.0,
                "failing_tests_caught": full_caught,
                "recall_percent": round((full_caught / total_failing) * 100.0, 2),
            },
            "random_sampling": {
                "name": "Random Selection (under budget)",
                "tests_selected": len(random_selected),
                "duration_seconds": round(random_time / 1000.0, 2),
                "time_savings_percent": round(
                    ((total_duration_ms - random_time) / total_duration_ms) * 100.0, 2
                ),
                "failing_tests_caught": random_caught,
                "recall_percent": round((random_caught / total_failing) * 100.0, 2),
            },
            "filename_matching": {
                "name": "Path Heuristic (under budget)",
                "tests_selected": len(filename_selected),
                "duration_seconds": round(filename_time / 1000.0, 2),
                "time_savings_percent": round(
                    ((total_duration_ms - filename_time) / total_duration_ms) * 100.0, 2
                ),
                "failing_tests_caught": filename_caught,
                "recall_percent": round((filename_caught / total_failing) * 100.0, 2),
            },
            "dependency_selection": {
                "name": "Dependency-Only (under budget)",
                "tests_selected": len(dep_selected),
                "duration_seconds": round(dep_time / 1000.0, 2),
                "time_savings_percent": round(
                    ((total_duration_ms - dep_time) / total_duration_ms) * 100.0, 2
                ),
                "failing_tests_caught": dep_caught,
                "recall_percent": round((dep_caught / total_failing) * 100.0, 2),
            },
            "codeimpact_optimizer": {
                "name": "CodeImpact Marginal Optimizer",
                "tests_selected": len(codeimpact_selected),
                "duration_seconds": round(codeimpact_time / 1000.0, 2),
                "time_savings_percent": plan.time_savings_percent,
                "failing_tests_caught": codeimpact_caught,
                "recall_percent": round((codeimpact_caught / total_failing) * 100.0, 2),
            },
        },
    }

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Test Selection Strategies")
    parser.add_argument(
        "--budget", type=float, default=30.0, help="Time budget in seconds"
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="datasets/test_selection_benchmark.json",
        help="Path to save benchmark JSON output",
    )
    args = parser.parse_args()

    results = run_benchmark(budget_seconds=args.budget)

    out_path = Path(args.output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Saved benchmark results to {out_path}")

    print("\n" + "=" * 75)
    print(f" INTELLIGENT TEST SELECTION BENCHMARK (Time Budget: {args.budget}s)")
    print("=" * 75)
    print(
        f"{'Strategy':<32} | {'Tests':<6} | {'Time (s)':<9} | {'Savings %':<10} | {'Recall %':<8}"
    )
    print("-" * 75)
    for data in results["strategies"].values():
        print(
            f"{data['name']:<32} | "
            f"{data['tests_selected']:<6} | "
            f"{data['duration_seconds']:<9.2f} | "
            f"{data['time_savings_percent']:<10.1f} | "
            f"{data['recall_percent']:<8.1f}"
        )
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
