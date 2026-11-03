from __future__ import annotations

from pathlib import Path

from app.services.analysis.orchestrator import StaticAnalysisOrchestrator

SAMPLE_REPO_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "examples" / "sample_python_repo"
)


def test_static_analysis_orchestrator_on_controlled_sample():
    # Read sample repository files
    auth_path = str(SAMPLE_REPO_DIR / "auth.py")
    payment_path = str(SAMPLE_REPO_DIR / "payment.py")
    notify_path = str(SAMPLE_REPO_DIR / "notification.py")

    with open(auth_path) as f:
        auth_head_content = f.read()
    with open(payment_path) as f:
        payment_head_content = f.read()
    with open(notify_path) as f:
        notify_head_content = f.read()

    # Base content without validate_session_token
    auth_base_content = auth_head_content.replace(
        """def validate_session_token(token: str) -> bool:
    if not token or len(token) < 16:
        return False
    return True
""",
        "",
    )

    sample_diff = """diff --git a/auth.py b/auth.py
--- a/auth.py
+++ b/auth.py
@@ -17,0 +18,6 @@
+def validate_session_token(token: str) -> bool:
+    if not token or len(token) < 16:
+        return False
+    return True
+
"""

    base_files = {"auth.py": auth_base_content}
    head_files = {
        "auth.py": auth_head_content,
        "payment.py": payment_head_content,
        "notification.py": notify_head_content,
    }

    orchestrator = StaticAnalysisOrchestrator()
    result = orchestrator.analyze(
        diff_text=sample_diff,
        base_files=base_files,
        head_files=head_files,
    )

    features = result["features"]
    dep_graph = result["dependency_graph"]
    impact_summary = result["impact_summary"]

    # Verify change size features
    assert features["files_changed_count"] == 1
    assert features["lines_added"] == 5
    assert features["functions_added_count"] == 1
    assert any("validate_session_token" in fn for fn in impact_summary["added_functions"])

    # Verify dependency graph features
    assert features["dependency_total_nodes"] > 5
    assert features["dependency_total_edges"] > 3
    assert "nodes" in dep_graph
    assert "edges" in dep_graph

    # Verify execution duration
    assert result["execution_duration_ms"] >= 0
