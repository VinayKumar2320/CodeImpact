from __future__ import annotations

import ast
from dataclasses import dataclass, field

import radon.complexity as cc
from radon.raw import analyze as raw_analyze

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FunctionComplexityMetrics:
    name: str
    cyclomatic_complexity: int
    rank: str  # A (1-5), B (6-10), C (11-20), D (21-30), E (31-40), F (41+)
    start_line: int
    end_line: int
    length_lines: int
    nesting_depth: int
    parameter_count: int
    is_high_complexity: bool = False  # CC >= 10


@dataclass
class FileComplexityMetrics:
    file_path: str
    sloc: int = 0
    comments_lines: int = 0
    average_complexity: float = 0.0
    max_complexity: int = 0
    high_complexity_functions_count: int = 0
    functions: list[FunctionComplexityMetrics] = field(default_factory=list)


@dataclass
class ComplexityDeltaReport:
    file_path: str
    base_average_cc: float = 0.0
    head_average_cc: float = 0.0
    delta_average_cc: float = 0.0
    base_max_cc: int = 0
    head_max_cc: int = 0
    delta_max_cc: int = 0
    modified_high_complexity_count: int = 0


class NestingDepthVisitor(ast.NodeVisitor):
    """
    Computes maximum block nesting depth for functions in Python AST.
    """

    def __init__(self):
        self.max_depth = 0
        self._current_depth = 0

    def _visit_block(self, node: ast.AST):
        self._current_depth += 1
        self.max_depth = max(self.max_depth, self._current_depth)
        self.generic_visit(node)
        self._current_depth -= 1

    visit_If = _visit_block
    visit_For = _visit_block
    visit_AsyncFor = _visit_block
    visit_While = _visit_block
    visit_Try = _visit_block
    visit_With = _visit_block
    visit_AsyncWith = _visit_block
    visit_Match = _visit_block


def calculate_function_nesting_depth(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    visitor = NestingDepthVisitor()
    for child in func_node.body:
        visitor.visit(child)
    return int(visitor.max_depth)


class ComplexityAnalyzer:
    """
    Computes Cyclomatic Complexity (via Radon) and structural metrics (nesting depth,
    parameter count, SLOC) for Python source code.
    """

    HIGH_COMPLEXITY_THRESHOLD = 10

    def analyze_source(self, source_code: str, file_path: str = "") -> FileComplexityMetrics:
        if not source_code or not source_code.strip():
            return FileComplexityMetrics(file_path=file_path)

        metrics = FileComplexityMetrics(file_path=file_path)

        # 1. Raw SLOC Analysis
        try:
            raw_res = raw_analyze(source_code)
            metrics.sloc = raw_res.sloc
            metrics.comments_lines = raw_res.comments
        except Exception as e:
            logger.debug(f"Radon raw analysis failed on {file_path}: {e}")

        # 2. Python AST Parsing for nesting and parameters
        ast_funcs: dict[str, tuple[int, int]] = {}  # name -> (nesting, params)
        try:
            tree = ast.parse(source_code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    nesting = calculate_function_nesting_depth(node)
                    params = (
                        len(node.args.args) + len(node.args.posonlyargs) + len(node.args.kwonlyargs)
                    )
                    if node.args.vararg:
                        params += 1
                    if node.args.kwarg:
                        params += 1
                    ast_funcs[node.name] = (nesting, params)
        except Exception as e:
            logger.debug(f"Python AST parse for nesting depth failed on {file_path}: {e}")

        # 3. Radon Cyclomatic Complexity
        try:
            blocks = cc.cc_visit(source_code)
            func_complexities: list[int] = []

            for b in blocks:
                # Radon returns Function or Class objects
                if getattr(b, "letter", "") in ("F", "M"):  # Function or Method
                    length = (
                        (b.endline - b.lineno) + 1 if hasattr(b, "endline") and b.endline else 1
                    )
                    nesting, param_count = ast_funcs.get(b.name, (0, 0))
                    is_high = b.complexity >= self.HIGH_COMPLEXITY_THRESHOLD

                    fn_metric = FunctionComplexityMetrics(
                        name=b.name,
                        cyclomatic_complexity=b.complexity,
                        rank=cc.cc_rank(b.complexity),
                        start_line=b.lineno,
                        end_line=getattr(b, "endline", b.lineno),
                        length_lines=length,
                        nesting_depth=nesting,
                        parameter_count=param_count,
                        is_high_complexity=is_high,
                    )
                    metrics.functions.append(fn_metric)
                    func_complexities.append(b.complexity)
                    if is_high:
                        metrics.high_complexity_functions_count += 1

            if func_complexities:
                metrics.average_complexity = round(
                    sum(func_complexities) / len(func_complexities), 2
                )
                metrics.max_complexity = max(func_complexities)

        except Exception as e:
            logger.warning(f"Radon cc_visit failed on {file_path}: {e}")

        return metrics

    def compute_delta(
        self,
        base_source: str | None,
        head_source: str | None,
        file_path: str = "",
        modified_func_names: list[str] | None = None,
    ) -> ComplexityDeltaReport:
        base_metrics = self.analyze_source(base_source or "", file_path) if base_source else None
        head_metrics = self.analyze_source(head_source or "", file_path) if head_source else None

        base_avg = base_metrics.average_complexity if base_metrics else 0.0
        head_avg = head_metrics.average_complexity if head_metrics else 0.0
        base_max = base_metrics.max_complexity if base_metrics else 0
        head_max = head_metrics.max_complexity if head_metrics else 0

        # Count modified functions that are high complexity
        modified_high_count = 0
        if head_metrics:
            mod_names_set = set(modified_func_names or [])
            for fn in head_metrics.functions:
                if fn.is_high_complexity and (not mod_names_set or fn.name in mod_names_set):
                    modified_high_count += 1

        return ComplexityDeltaReport(
            file_path=file_path,
            base_average_cc=base_avg,
            head_average_cc=head_avg,
            delta_average_cc=round(head_avg - base_avg, 2),
            base_max_cc=base_max,
            head_max_cc=head_max,
            delta_max_cc=head_max - base_max,
            modified_high_complexity_count=modified_high_count,
        )


complexity_analyzer = ComplexityAnalyzer()
