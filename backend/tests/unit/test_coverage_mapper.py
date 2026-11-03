from app.services.analysis.diff_parser import DiffHunk, FileDiff
from app.services.test_selection.coverage_mapper import TestCandidate, TestCoverageMapper


def test_map_dynamic_coverage():
    mapper = TestCoverageMapper()
    hunk = DiffHunk(
        base_start=1,
        base_length=5,
        head_start=1,
        head_length=5,
        head_added_lines=[10, 11, 12],
    )
    diff = FileDiff(
        old_path="app/auth.py",
        new_path="app/auth.py",
        status="modified",
        additions=3,
        deletions=1,
        hunks=[hunk],
    )
    coverage_data = {
        "files": {
            "app/auth.py": {
                "executed_lines": [5, 6, 10, 11, 20],
                "missing_lines": [12],
            }
        }
    }

    candidates = mapper.map_dynamic_coverage(coverage_data, [diff])
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.evidence_level == "EVIDENCE_DYNAMIC_COVERAGE"
    assert "app/auth.py:10" in cand.covered_symbols
    assert "app/auth.py:11" in cand.covered_symbols
    assert "Dynamic coverage verified" in cand.selection_reason


def test_map_static_call_graph():
    mapper = TestCoverageMapper()
    test_cand = TestCandidate(
        test_identifier="tests/test_tokens.py::test_verify_token",
        file_path="tests/test_tokens.py",
        test_name="test_verify_token",
    )
    edges = [
        {"source": "test_verify_token", "target": "verify_token_fn"},
        {"source": "verify_token_fn", "target": "decode_jwt"},
    ]
    matched = mapper.map_static_call_graph(
        changed_symbols=["verify_token_fn"],
        dependency_graph_edges=edges,
        available_tests=[test_cand],
    )
    assert len(matched) == 1
    assert matched[0].evidence_level == "EVIDENCE_STATIC_CALL_GRAPH"
    assert "Static call graph" in matched[0].selection_reason


def test_map_file_heuristics():
    mapper = TestCoverageMapper()
    diff = FileDiff(
        old_path="app/services/billing.py",
        new_path="app/services/billing.py",
        status="modified",
        additions=1,
        deletions=0,
    )
    all_tests = [
        "tests/test_auth.py",
        "tests/services/test_billing.py",
        "tests/test_users.py",
    ]
    candidates = mapper.map_file_heuristics([diff], all_tests)
    assert len(candidates) == 1
    assert candidates[0].file_path == "tests/services/test_billing.py"
    assert candidates[0].evidence_level == "EVIDENCE_DEPENDENCY_HEURISTIC"
