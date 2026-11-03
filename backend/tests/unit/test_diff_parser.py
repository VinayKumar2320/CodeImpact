from __future__ import annotations

from app.services.analysis.diff_parser import UnifiedDiffParser
from tests.fixtures.github_payloads import SAMPLE_DIFF_CONTENT


def test_diff_parser_extracts_hunks_and_lines():
    parser = UnifiedDiffParser()
    parsed = parser.parse(SAMPLE_DIFF_CONTENT)

    assert parsed.files_changed_count == 1
    assert parsed.lines_added == 5
    assert parsed.lines_deleted == 0
    assert parsed.change_size == 5

    file_diff = parsed.files[0]
    assert file_diff.new_path == "app/auth.py"
    assert file_diff.status == "modified"
    assert file_diff.is_test_file is False
    assert file_diff.is_config_file is False
    assert file_diff.extension == ".py"

    # Line numbers in head: 12, 13, 14, 15, 16, 17
    assert 12 in file_diff.modified_head_lines
    assert 15 in file_diff.modified_head_lines


def test_diff_parser_file_classification():
    diff_text = """diff --git a/tests/test_auth.py b/tests/test_auth.py
new file mode 100644
--- /dev/null
+++ b/tests/test_auth.py
@@ -0,0 +1,5 @@
+def test_dummy():
+    pass
diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -1,1 +1,2 @@
 [tool]
+version = "1.0.0"
"""
    parser = UnifiedDiffParser()
    parsed = parser.parse(diff_text)

    assert parsed.files_changed_count == 2
    assert parsed.test_files_changed_count == 1
    assert parsed.config_files_changed_count == 1

    test_f = parsed.get_file("tests/test_auth.py")
    assert test_f is not None
    assert test_f.status == "added"
    assert test_f.is_test_file is True

    cfg_f = parsed.get_file("pyproject.toml")
    assert cfg_f is not None
    assert cfg_f.is_config_file is True


def test_diff_parser_handles_empty_diff():
    parser = UnifiedDiffParser()
    assert parser.parse("").files_changed_count == 0
    assert parser.parse("   ").lines_added == 0
