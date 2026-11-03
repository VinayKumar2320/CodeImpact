from __future__ import annotations

from app.services.analysis.ast_parser import PythonASTParser
from app.services.analysis.diff_parser import DiffHunk, FileDiff


def test_ast_parser_extracts_functions_and_classes():
    code = """
import os
from datetime import datetime

class TokenManager:
    def __init__(self, secret: str):
        self.secret = secret

    def generate_token(self, user_id: str) -> str:
        return f"{self.secret}_{user_id}"

    def _internal_clean(self):
        pass

def standalone_func(x, y=10):
    return x + y
"""
    parser = PythonASTParser()
    summary = parser.parse_source(code, "app/tokens.py")

    assert summary.has_parse_errors is False
    assert len(summary.classes) == 1
    cls = summary.classes[0]
    assert cls.name == "TokenManager"
    assert cls.is_public is True

    # Functions: __init__, generate_token, _internal_clean, standalone_func
    funcs = {f.name: f for f in summary.functions}
    assert "generate_token" in funcs
    assert funcs["generate_token"].is_public is True
    assert funcs["generate_token"].parent_class == "TokenManager"

    assert "_internal_clean" in funcs
    assert funcs["_internal_clean"].is_public is False

    assert "standalone_func" in funcs
    assert funcs["standalone_func"].parameters == ["x", "y"]


def test_ast_parser_analyzes_diff_impact():
    base_code = """
def unchanged_func():
    return 1

def func_to_modify():
    return 2

def func_to_delete():
    return 3
"""
    head_code = """
def unchanged_func():
    return 1

def func_to_modify():
    # Modified line
    return 200

def func_newly_added():
    return 4
"""
    # Simulate hunk modifying line 7 (inside func_to_modify)
    f_diff = FileDiff(
        old_path="app/math.py",
        new_path="app/math.py",
        status="modified",
        additions=2,
        deletions=1,
        hunks=[
            DiffHunk(
                base_start=5,
                base_length=3,
                head_start=5,
                head_length=3,
                head_added_lines=[6, 7],
            )
        ],
    )

    parser = PythonASTParser()
    impact = parser.analyze_diff_impact(base_code, head_code, f_diff)

    modified_names = [f.name for f in impact.functions_modified]
    added_names = [f.name for f in impact.functions_added]
    deleted_names = [f.name for f in impact.functions_deleted]

    assert "func_to_modify" in modified_names
    assert "func_newly_added" in added_names
    assert "func_to_delete" in deleted_names
    assert "unchanged_func" not in modified_names
    assert impact.public_api_changes_count >= 2


def test_ast_parser_resilient_to_syntax_errors():
    malformed_code = "def broken(x:\n    if ((\n"
    parser = PythonASTParser()
    summary = parser.parse_source(malformed_code, "broken.py")
    assert summary.has_parse_errors is True
