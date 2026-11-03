from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger
from app.schemas.github import GitHubCommitSummary
from app.services.analysis.ast_parser import (
    ASTDiffImpact,
    ModuleASTSummary,
    PythonASTParser,
    python_ast_parser,
)
from app.services.analysis.churn_analyzer import GitChurnAnalyzer, git_churn_analyzer
from app.services.analysis.complexity import ComplexityAnalyzer, complexity_analyzer
from app.services.analysis.diff_parser import ParsedDiff, UnifiedDiffParser, diff_parser
from app.services.analysis.ts_parser import TypeScriptASTParser, ts_ast_parser
from app.services.dependencies.graph_builder import (
    DependencyAnalysisResult,
    DependencyGraphBuilder,
    dependency_graph_builder,
)

logger = get_logger(__name__)


class StaticAnalysisOrchestrator:
    """
    Coordinates static code analysis across unified diffs, Tree-sitter ASTs,
    Radon cyclomatic complexity, NetworkX dependency graphs, and Git churn.
    """

    def __init__(
        self,
        diff_engine: UnifiedDiffParser | None = None,
        py_parser: PythonASTParser | None = None,
        ts_parser: TypeScriptASTParser | None = None,
        complexity_engine: ComplexityAnalyzer | None = None,
        dep_builder: DependencyGraphBuilder | None = None,
        churn_engine: GitChurnAnalyzer | None = None,
    ):
        self.diff_parser = diff_engine or diff_parser
        self.py_ast_parser = py_parser or python_ast_parser
        self.ts_ast_parser = ts_parser or ts_ast_parser
        self.complexity_analyzer = complexity_engine or complexity_analyzer
        self.dependency_builder = dep_builder or dependency_graph_builder
        self.churn_analyzer = churn_engine or git_churn_analyzer

    def analyze(
        self,
        diff_text: str,
        base_files: dict[str, str],
        head_files: dict[str, str],
        commits_by_file: dict[str, list[GitHubCommitSummary]] | None = None,
    ) -> dict[str, Any]:
        start_time = time.time()
        logger.info("Executing static analysis pipeline")

        # 1. Diff Analysis
        parsed_diff: ParsedDiff = self.diff_parser.parse(diff_text)

        # 2. AST Extraction & Impact Mapping
        all_modified_funcs: list[str] = []
        all_added_funcs: list[str] = []
        all_deleted_funcs: list[str] = []
        all_modified_classes: list[str] = []
        total_public_api_changes = 0

        file_impacts: list[ASTDiffImpact] = []
        module_summaries: list[ModuleASTSummary] = []

        # Parse ASTs for all available head files to build comprehensive dependency graph
        for file_path, content in head_files.items():
            if file_path.endswith(".py"):
                mod_summary = self.py_ast_parser.parse_source(content, file_path)
                module_summaries.append(mod_summary)
            elif file_path.endswith((".ts", ".tsx")):
                mod_summary = self.ts_ast_parser.parse_source(content, file_path)
                module_summaries.append(mod_summary)

        # Map changes for touched files
        for f_diff in parsed_diff.files:
            file_path = f_diff.file_path
            base_content = base_files.get(f_diff.old_path or file_path)
            head_content = head_files.get(f_diff.new_path or file_path)

            if file_path.endswith(".py"):
                impact = self.py_ast_parser.analyze_diff_impact(
                    base_source=base_content,
                    head_source=head_content,
                    file_diff=f_diff,
                )
                file_impacts.append(impact)
                all_modified_funcs.extend(
                    f"{file_path}::{fn.qualified_name}" for fn in impact.functions_modified
                )
                all_added_funcs.extend(
                    f"{file_path}::{fn.qualified_name}" for fn in impact.functions_added
                )
                all_deleted_funcs.extend(
                    f"{file_path}::{fn.qualified_name}" for fn in impact.functions_deleted
                )
                all_modified_classes.extend(
                    f"{file_path}::{cls.name}" for cls in impact.classes_modified
                )
                total_public_api_changes += impact.public_api_changes_count

            elif file_path.endswith((".ts", ".tsx")):
                impact = self.ts_ast_parser.analyze_diff_impact(
                    base_source=base_content,
                    head_source=head_content,
                    file_diff=f_diff,
                )
                file_impacts.append(impact)
                all_modified_funcs.extend(
                    f"{file_path}::{fn.qualified_name}" for fn in impact.functions_modified
                )
                all_added_funcs.extend(
                    f"{file_path}::{fn.qualified_name}" for fn in impact.functions_added
                )
                all_deleted_funcs.extend(
                    f"{file_path}::{fn.qualified_name}" for fn in impact.functions_deleted
                )
                all_modified_classes.extend(
                    f"{file_path}::{cls.name}" for cls in impact.classes_modified
                )
                total_public_api_changes += impact.public_api_changes_count

        # 3. Complexity Analysis
        file_complexities = []
        delta_avg_cc_list = []
        delta_max_cc_list = []
        modified_high_cc_count = 0

        for f_diff in parsed_diff.files:
            file_path = f_diff.file_path
            if file_path.endswith(".py"):
                base_content = base_files.get(f_diff.old_path or file_path)
                head_content = head_files.get(f_diff.new_path or file_path)

                delta_report = self.complexity_analyzer.compute_delta(
                    base_source=base_content,
                    head_source=head_content,
                    file_path=file_path,
                )
                delta_avg_cc_list.append(delta_report.delta_average_cc)
                delta_max_cc_list.append(delta_report.delta_max_cc)
                modified_high_cc_count += delta_report.modified_high_complexity_count

                if head_content:
                    file_metrics = self.complexity_analyzer.analyze_source(head_content, file_path)
                    file_complexities.append(file_metrics)

        all_func_complexities = [
            fn.cyclomatic_complexity for fm in file_complexities for fn in fm.functions
        ]
        mean_complexity = (
            round(sum(all_func_complexities) / len(all_func_complexities), 2)
            if all_func_complexities
            else 1.0
        )
        max_complexity = max(all_func_complexities) if all_func_complexities else 1
        delta_avg_cc = (
            round(sum(delta_avg_cc_list) / len(delta_avg_cc_list), 2) if delta_avg_cc_list else 0.0
        )
        delta_max_cc = max(delta_max_cc_list) if delta_max_cc_list else 0

        # 4. Dependency Graph Analysis
        modified_func_set = set(all_modified_funcs)
        dep_result: DependencyAnalysisResult = self.dependency_builder.build_graph(
            module_summaries=module_summaries,
            modified_func_ids=modified_func_set,
        )

        # 5. Git Churn Analysis
        churn_metrics = self.churn_analyzer.analyze_churn(commits_by_file or {})

        execution_duration_ms = int((time.time() - start_time) * 1000)

        # 6. Aggregate Structured Feature Vector
        features = {
            # Change Size
            "files_changed_count": parsed_diff.files_changed_count,
            "lines_added": parsed_diff.lines_added,
            "lines_deleted": parsed_diff.lines_deleted,
            "change_size": parsed_diff.change_size,
            "functions_modified_count": len(all_modified_funcs),
            "functions_added_count": len(all_added_funcs),
            "functions_deleted_count": len(all_deleted_funcs),
            "classes_modified_count": len(all_modified_classes),
            "public_api_changes_count": total_public_api_changes,
            "test_files_changed_count": parsed_diff.test_files_changed_count,
            "config_files_changed_count": parsed_diff.config_files_changed_count,
            # Complexity
            "average_complexity": mean_complexity,
            "max_complexity": max_complexity,
            "delta_average_complexity": delta_avg_cc,
            "delta_max_complexity": delta_max_cc,
            "modified_high_complexity_count": modified_high_cc_count,
            # Dependency Impact
            "dependency_total_nodes": dep_result.total_nodes,
            "dependency_total_edges": dep_result.total_edges,
            "directly_modified_nodes_count": dep_result.modified_nodes_count,
            "affected_callers_count": dep_result.affected_callers_count,
            "downstream_dependencies_count": dep_result.downstream_dependencies_count,
            "mean_betweenness_centrality": dep_result.mean_betweenness_centrality,
            "max_betweenness_centrality": dep_result.max_betweenness_centrality,
            "mean_fan_in": dep_result.mean_fan_in,
            "mean_fan_out": dep_result.mean_fan_out,
            # Historical Churn
            "mean_change_frequency": churn_metrics.mean_change_frequency,
            "max_change_frequency": churn_metrics.max_change_frequency,
            "distinct_contributors_count": churn_metrics.distinct_contributors_count,
            "mean_file_age_days": churn_metrics.mean_file_age_days,
            "recent_change_concentration": churn_metrics.recent_change_concentration,
        }

        impact_summary = {
            "modified_functions": all_modified_funcs,
            "added_functions": all_added_funcs,
            "deleted_functions": all_deleted_funcs,
            "affected_callers": dep_result.potentially_affected_callers,
            "downstream_dependencies": dep_result.downstream_dependencies,
        }

        return {
            "features": features,
            "dependency_graph": dep_result.serialized_graph,
            "impact_summary": impact_summary,
            "execution_duration_ms": execution_duration_ms,
        }


static_analysis_orchestrator = StaticAnalysisOrchestrator()
