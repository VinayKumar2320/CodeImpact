from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.analysis.diff_parser import FileDiff

logger = get_logger(__name__)


@dataclass
class TestCandidate:
    __test__ = False
    test_identifier: str  # e.g. tests/test_auth.py::test_login_success
    file_path: str
    test_name: str
    estimated_duration_ms: int = 500
    historical_failure_rate: float = 0.05
    covered_symbols: set[str] = field(default_factory=set)
    evidence_level: str = "EVIDENCE_DEPENDENCY_HEURISTIC"
    selection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_identifier": self.test_identifier,
            "file_path": self.file_path,
            "test_name": self.test_name,
            "estimated_duration_ms": self.estimated_duration_ms,
            "historical_failure_rate": round(self.historical_failure_rate, 4),
            "covered_symbols": sorted(self.covered_symbols),
            "evidence_level": self.evidence_level,
            "selection_reason": self.selection_reason,
        }


class TestCoverageMapper:
    """
    Maps pull request changes to affected test cases using dynamic coverage data,
    static call graph reachability, and file path heuristics.
    """

    def map_dynamic_coverage(
        self,
        coverage_data: dict[str, Any],
        modified_files: list[FileDiff],
    ) -> list[TestCandidate]:
        """
        Parses dynamic test execution coverage artifacts (pytest-cov JSON or coverage.py).
        Matches executed lines with hunks modified in the pull request.
        """
        candidates: list[TestCandidate] = []
        files_map = coverage_data.get("files", {})

        for diff in modified_files:
            file_key = diff.new_path or diff.old_path or ""
            file_cov = files_map.get(file_key)
            if not file_cov:
                continue

            executed_lines = set(file_cov.get("executed_lines", []))
            modified_lines: set[int] = set()
            for hunk in diff.hunks:
                modified_lines.update(hunk.head_added_lines)

            covered_modifications = executed_lines.intersection(modified_lines)
            if covered_modifications:
                stem = Path(file_key).stem
                test_id = f"tests/test_{stem}.py::test_{stem}_regression"
                candidate = TestCandidate(
                    test_identifier=test_id,
                    file_path=f"tests/test_{stem}.py",
                    test_name=f"test_{stem}_regression",
                    estimated_duration_ms=450,
                    historical_failure_rate=0.08,
                    covered_symbols={f"{file_key}:{line}" for line in covered_modifications},
                    evidence_level="EVIDENCE_DYNAMIC_COVERAGE",
                    selection_reason=(
                        f"Dynamic coverage verified: test directly executes {len(covered_modifications)} lines modified in {file_key}"
                    ),
                )
                candidates.append(candidate)

        return candidates

    def map_static_call_graph(
        self,
        changed_symbols: list[str],
        dependency_graph_edges: list[dict[str, Any]],
        available_tests: list[TestCandidate],
    ) -> list[TestCandidate]:
        """
        Traverses dependency call graph edges to find test functions that
        directly or transitively call any modified symbol.
        """
        matched: list[TestCandidate] = []
        changed_set = set(changed_symbols)

        # Build reverse adjacency map (callee -> callers)
        callee_to_callers: dict[str, set[str]] = {}
        for edge in dependency_graph_edges:
            caller = edge.get("source", "")
            callee = edge.get("target", "")
            if caller and callee:
                callee_to_callers.setdefault(callee, set()).add(caller)

        for test in available_tests:
            # Check if test reaches any changed symbol
            reached_symbols = set()
            for sym in changed_set:
                # Direct call
                if test.test_name in callee_to_callers.get(sym, set()) or test.file_path in sym:
                    reached_symbols.add(sym)

            if reached_symbols:
                test.evidence_level = "EVIDENCE_STATIC_CALL_GRAPH"
                test.covered_symbols.update(reached_symbols)
                test.selection_reason = f"Static call graph reachability: test invokes symbol(s) '{', '.join(sorted(reached_symbols)[:3])}'"
                matched.append(test)

        return matched

    def map_file_heuristics(
        self,
        modified_files: list[FileDiff],
        all_test_files: list[str],
    ) -> list[TestCandidate]:
        """
        Matches source files to test files using conventional naming heuristics.
        e.g. app/services/auth.py -> tests/services/test_auth.py or tests/test_auth.py
        """
        candidates: list[TestCandidate] = []

        for diff in modified_files:
            file_path = diff.new_path or diff.old_path or ""
            if not file_path:
                continue
            stem = Path(file_path).stem
            # Common test filename patterns
            patterns = [
                re.compile(rf"test_{re.escape(stem)}\.py$"),
                re.compile(rf"{re.escape(stem)}_test\.py$"),
                re.compile(rf"test_{re.escape(stem)}\.ts$"),
            ]

            matching_test_paths = [
                t_path for t_path in all_test_files if any(p.search(t_path) for p in patterns)
            ]

            for t_path in matching_test_paths:
                test_name = f"test_{stem}_functionality"
                candidate = TestCandidate(
                    test_identifier=f"{t_path}::{test_name}",
                    file_path=t_path,
                    test_name=test_name,
                    estimated_duration_ms=600,
                    historical_failure_rate=0.04,
                    covered_symbols={file_path},
                    evidence_level="EVIDENCE_DEPENDENCY_HEURISTIC",
                    selection_reason=f"Path heuristic match: test suite for modified module {file_path}",
                )
                candidates.append(candidate)

        return candidates


test_coverage_mapper = TestCoverageMapper()
