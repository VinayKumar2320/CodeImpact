from __future__ import annotations

from app.services.analysis.diff_parser import DiffHunk, FileDiff
from app.services.analysis.ts_parser import TypeScriptASTParser


def test_ts_parser_extracts_classes_and_arrow_functions():
    code = """
export class UserService {
    private secretKey: string;

    public getUser(id: string): object {
        return { id };
    }

    private _internalAudit(): void {}
}

export const formatUserName = (name: string): string => {
    return name.trim();
};
"""
    parser = TypeScriptASTParser()
    summary = parser.parse_source(code, "src/user.ts")

    assert summary.has_parse_errors is False
    assert len(summary.classes) == 1
    cls = summary.classes[0]
    assert cls.name == "UserService"
    assert cls.is_public is True

    # Functions
    funcs = {f.name: f for f in summary.functions}
    assert "getUser" in funcs
    assert funcs["getUser"].is_public is True

    assert "_internalAudit" in funcs
    assert funcs["_internalAudit"].is_public is False

    assert "formatUserName" in funcs
    assert funcs["formatUserName"].is_public is True


def test_ts_parser_diff_impact():
    base_code = """
export function add(a: number, b: number): number {
    return a + b;
}
"""
    head_code = """
export function add(a: number, b: number): number {
    // Modified logic
    return a + b + 1;
}

export function multiply(a: number, b: number): number {
    return a * b;
}
"""
    f_diff = FileDiff(
        old_path="src/math.ts",
        new_path="src/math.ts",
        status="modified",
        additions=4,
        deletions=1,
        hunks=[
            DiffHunk(
                base_start=2,
                base_length=2,
                head_start=2,
                head_length=6,
                head_added_lines=[3, 4, 6, 7],
            )
        ],
    )
    parser = TypeScriptASTParser()
    impact = parser.analyze_diff_impact(base_code, head_code, f_diff)

    modified_names = [f.name for f in impact.functions_modified]
    added_names = [f.name for f in impact.functions_added]

    assert "add" in modified_names
    assert "multiply" in added_names
    assert impact.public_api_changes_count == 2
