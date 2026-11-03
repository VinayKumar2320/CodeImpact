from __future__ import annotations

import time
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.ml.inference.predictor import RiskPredictionResult, risk_predictor
from app.models.analysis import Analysis, AnalysisStatus
from app.models.prediction import Prediction
from app.models.test_case import TestRecommendation
from app.services.analysis.diff_parser import diff_parser
from app.services.analysis.orchestrator import static_analysis_orchestrator
from app.services.test_selection.coverage_mapper import TestCandidate, test_coverage_mapper
from app.services.test_selection.optimizer import TestSelectionPlan, test_selection_optimizer

logger = get_logger(__name__)


class AnalysisOrchestrationService:
    """
    End-to-end orchestration service coordinating:
    1. Static code analysis (Diff, AST, Complexity, Dependency Graph)
    2. ML regression risk prediction (calibrated XGBoost + TreeSHAP attributions)
    3. Intelligent budgeted test selection (coverage mapping + greedy marginal optimizer)
    4. Database persistence and report generation
    """

    async def execute_analysis_pipeline(
        self,
        analysis_id: str,
        diff_text: str,
        base_files: dict[str, str],
        head_files: dict[str, str],
        coverage_data: dict[str, Any] | None = None,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        start_time = time.time()
        logger.info(f"Starting analysis orchestration pipeline for analysis {analysis_id}")

        # 1. Run Static Analysis Engine
        static_result = static_analysis_orchestrator.analyze(
            diff_text=diff_text,
            base_files=base_files,
            head_files=head_files,
        )

        tabular_features = static_result.get("features", {})

        # 2. Run Machine Learning Risk Prediction
        prediction_result: RiskPredictionResult = risk_predictor.predict(tabular_features)

        # 3. Discover Candidate Tests & Run Budgeted Test Selection
        parsed_diff = diff_parser.parse(diff_text)
        modified_diffs = parsed_diff.files
        changed_symbols = [
            f"{f.file_path}:{item.get('name')}"
            for f in modified_diffs
            for item in static_result.get("impact_summary", {}).get("modified_functions", [])
        ]
        if not changed_symbols:
            changed_symbols = [f.file_path for f in modified_diffs]

        # Candidate discovery
        candidates: list[TestCandidate] = []
        if coverage_data:
            dynamic_candidates = test_coverage_mapper.map_dynamic_coverage(
                coverage_data, modified_diffs
            )
            candidates.extend(dynamic_candidates)

        dep_edges = static_result.get("dependency_graph", {}).get("edges", [])
        static_candidates = test_coverage_mapper.map_static_call_graph(
            changed_symbols=changed_symbols,
            dependency_graph_edges=dep_edges,
            available_tests=candidates,
        )
        candidates.extend(static_candidates)

        # File heuristics
        known_test_files = [p for p in head_files if "test" in p.lower()]
        heuristic_candidates = test_coverage_mapper.map_file_heuristics(
            modified_diffs, known_test_files
        )
        candidates.extend(heuristic_candidates)

        # Deduplicate candidates
        seen_ids = set()
        unique_candidates: list[TestCandidate] = []
        for c in candidates:
            if c.test_identifier not in seen_ids:
                seen_ids.add(c.test_identifier)
                unique_candidates.append(c)

        # Execute Optimizer (budget 60s)
        test_plan: TestSelectionPlan = test_selection_optimizer.select_tests(
            candidates=unique_candidates,
            target_symbols=changed_symbols,
            budget_seconds=60.0,
            risk_score=prediction_result.risk_score,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        # 4. Persist to Database if session provided
        if db is not None:
            await self._persist_results(
                analysis_id=analysis_id,
                static_result=static_result,
                prediction_result=prediction_result,
                test_plan=test_plan,
                elapsed_ms=elapsed_ms,
                db=db,
            )

        summary_markdown = self.generate_markdown_summary(
            prediction_result=prediction_result,
            test_plan=test_plan,
            static_result=static_result,
        )

        return {
            "analysis_id": analysis_id,
            "status": "COMPLETED",
            "execution_duration_ms": elapsed_ms,
            "static_analysis": static_result,
            "prediction": prediction_result.to_dict(),
            "test_selection": test_plan.to_dict(),
            "summary_markdown": summary_markdown,
        }

    async def _persist_results(
        self,
        analysis_id: str,
        static_result: dict[str, Any],
        prediction_result: RiskPredictionResult,
        test_plan: TestSelectionPlan,
        elapsed_ms: int,
        db: AsyncSession,
    ) -> None:
        # Load Analysis
        stmt = (
            select(Analysis)
            .options(selectinload(Analysis.prediction), selectinload(Analysis.recommended_tests))
            .where(Analysis.id == analysis_id)
        )
        res = await db.execute(stmt)
        analysis = res.scalar_one_or_none()
        if not analysis:
            logger.warning(f"Analysis {analysis_id} not found in database during persistence.")
            return

        # Update Analysis
        analysis.status = AnalysisStatus.COMPLETED.value
        analysis.execution_duration_ms = elapsed_ms
        analysis.dependency_graph = static_result.get("dependency_graph", {})
        # Package full features and graphs
        features_payload = {
            "tabular_features": static_result.get("features", {}),
            "ast_impact": static_result.get("impact_summary", {}),
            "dependencies": static_result.get("dependency_graph", {}),
            "test_selection_analytics": {
                "total_suite_count": test_plan.total_suite_tests_count,
                "time_savings_percent": test_plan.time_savings_percent,
                "test_reduction_percent": test_plan.test_reduction_percent,
                "total_suite_duration_ms": test_plan.total_suite_duration_ms,
                "selected_suite_duration_ms": test_plan.selected_suite_duration_ms,
            },
        }
        analysis.features = features_payload

        # Update or Create Prediction
        if analysis.prediction:
            pred = analysis.prediction
            pred.risk_score = prediction_result.risk_score
            pred.risk_tier = prediction_result.risk_tier.value
            pred.calibrated_probability = prediction_result.risk_score
            pred.feature_attributions = {
                "top_risk_factors": [f.to_dict() for f in prediction_result.top_risk_factors],
                "top_protective_factors": [
                    f.to_dict() for f in prediction_result.top_protective_factors
                ],
                "confidence_lower": prediction_result.confidence_lower,
                "confidence_upper": prediction_result.confidence_upper,
                "model_name": prediction_result.model_name,
                "model_version": prediction_result.model_version,
            }
        else:
            pred = Prediction(
                analysis_id=analysis.id,
                risk_score=prediction_result.risk_score,
                risk_tier=prediction_result.risk_tier.value,
                calibrated_probability=prediction_result.risk_score,
                confidence=1.0
                - (prediction_result.confidence_upper - prediction_result.confidence_lower),
                feature_attributions={
                    "top_risk_factors": [f.to_dict() for f in prediction_result.top_risk_factors],
                    "top_protective_factors": [
                        f.to_dict() for f in prediction_result.top_protective_factors
                    ],
                    "confidence_lower": prediction_result.confidence_lower,
                    "confidence_upper": prediction_result.confidence_upper,
                    "model_name": prediction_result.model_name,
                    "model_version": prediction_result.model_version,
                },
            )
            db.add(pred)

        # Clear old recommendations and insert fresh
        await db.execute(
            delete(TestRecommendation).where(TestRecommendation.analysis_id == analysis.id)
        )

        for item in test_plan.recommended_tests:
            rec = TestRecommendation(
                analysis_id=analysis.id,
                test_identifier=item.test_identifier,
                rank=item.rank,
                selection_reason=item.selection_reason,
                evidence_level=item.evidence_level,
                estimated_duration_ms=item.estimated_duration_ms,
                priority_score=item.priority_score,
            )
            db.add(rec)

        await db.commit()
        await db.refresh(analysis)
        logger.info(f"Persisted analysis, prediction, and test recommendations for {analysis_id}")

    def generate_markdown_summary(
        self,
        prediction_result: RiskPredictionResult,
        test_plan: TestSelectionPlan,
        static_result: dict[str, Any],
    ) -> str:
        """Generates GitHub Check Run markdown summary with collapsible sections."""
        tier = prediction_result.risk_tier.value
        score_pct = int(prediction_result.risk_score * 100)
        badge = (
            "🟢"
            if tier == "LOW"
            else ("🟡" if tier == "MEDIUM" else ("🟠" if tier == "HIGH" else "🔴"))
        )

        lines = [
            f"## {badge} CodeImpact Analysis Summary — Risk: {tier} ({score_pct}%)",
            "",
            f"**Model:** `{prediction_result.model_name}` v`{prediction_result.model_version}` | "
            f"**Confidence Interval:** `[{prediction_result.confidence_lower:.2f}, {prediction_result.confidence_upper:.2f}]`",
            "",
            "### 🔍 Key Risk Factors",
        ]

        if prediction_result.top_risk_factors:
            for f in prediction_result.top_risk_factors[:4]:
                lines.append(
                    f"- **{f.feature_name.replace('_', ' ').capitalize()}** ({f.feature_value}): {f.human_explanation}"
                )
        else:
            lines.append("- No critical risk factors identified.")

        if prediction_result.top_protective_factors:
            lines.append("\n### 🛡️ Protective Factors")
            for f in prediction_result.top_protective_factors[:3]:
                lines.append(
                    f"- **{f.feature_name.replace('_', ' ').capitalize()}**: {f.human_explanation}"
                )

        lines.extend(
            [
                "",
                "### ⚡ Intelligent Test Selection",
                f"- Recommended **{test_plan.selected_tests_count}** of **{test_plan.total_suite_tests_count}** tests "
                f"({test_plan.test_reduction_percent:.1f}% reduction).",
                f"- Estimated execution time: **{test_plan.selected_suite_duration_ms / 1000.0:.2f}s** vs full suite "
                f"**{test_plan.total_suite_duration_ms / 1000.0:.2f}s** (**{test_plan.time_savings_percent:.1f}% time saved**).",
                "",
            ]
        )

        if test_plan.recommended_tests:
            lines.append("| Rank | Test Case | Evidence | Est. Duration | Reason |")
            lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for t in test_plan.recommended_tests[:8]:
                ev_label = t.evidence_level.replace("EVIDENCE_", "")
                lines.append(
                    f"| {t.rank} | `{t.test_name}` | `{ev_label}` | {t.estimated_duration_ms}ms | {t.selection_reason} |"
                )

        lines.extend(
            [
                "",
                "<details>",
                "<summary><b>📊 Static Analysis & Code Impact Details</b></summary>",
                "",
                f"- **Files Modified:** {len(static_result.get('diff', {}).get('files', []))}",
                f"- **Max Cyclomatic Complexity:** {static_result.get('complexity', {}).get('max_cyclomatic_complexity', 1)}",
                f"- **Affected Downstream Callers:** {static_result.get('dependencies', {}).get('affected_callers_count', 0)}",
                f"- **Betweenness Centrality:** {static_result.get('dependencies', {}).get('betweenness_centrality', 0.0):.4f}",
                "",
                "</details>",
            ]
        )

        return "\n".join(lines)


analysis_orchestration_service = AnalysisOrchestrationService()
