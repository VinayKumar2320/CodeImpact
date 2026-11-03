from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.analysis import Analysis
from app.models.prediction import Prediction
from app.models.test_case import TestRecommendation
from app.schemas.analysis import (
    AnalysisFeaturesResponse,
    AnalysisReportResponse,
    AnalysisResponse,
    DependencyGraphResponse,
    GraphEdge,
    GraphNode,
    RecommendedTestsResponse,
    RiskFactorDetail,
    RiskPredictionResponse,
    TestRecommendationResponse,
)

router = APIRouter(prefix="/analyses", tags=["Analyses"])


@router.get("/{analysis_id}", response_model=AnalysisResponse, summary="Get Analysis Overview")
async def get_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    stmt = (
        select(Analysis)
        .options(selectinload(Analysis.prediction))
        .where(Analysis.id == analysis_id)
    )
    result = await db.execute(stmt)
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis record not found")

    risk_score = analysis.prediction.risk_score if analysis.prediction else None
    risk_tier = analysis.prediction.risk_tier if analysis.prediction else None

    return AnalysisResponse(
        id=analysis.id,
        pull_request_id=analysis.pull_request_id,
        commit_sha=analysis.commit_sha,
        status=analysis.status,
        analysis_version=analysis.analysis_version,
        execution_duration_ms=analysis.execution_duration_ms,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
        risk_score=risk_score,
        risk_tier=risk_tier,
    )


@router.get(
    "/{analysis_id}/features",
    response_model=AnalysisFeaturesResponse,
    summary="Get Extracted Feature Vector",
)
async def get_analysis_features(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnalysisFeaturesResponse:
    stmt = select(Analysis).where(Analysis.id == analysis_id)
    analysis = (await db.execute(stmt)).scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    features_data = analysis.features or {}
    tabular = features_data.get("tabular_features", {})

    return AnalysisFeaturesResponse(
        analysis_id=analysis.id,
        commit_sha=analysis.commit_sha,
        features=tabular,
    )


@router.get(
    "/{analysis_id}/risk",
    response_model=RiskPredictionResponse,
    summary="Get Risk Prediction and SHAP Attributions",
)
async def get_analysis_risk(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> RiskPredictionResponse:
    stmt = select(Prediction).where(Prediction.analysis_id == analysis_id)
    prediction = (await db.execute(stmt)).scalar_one_or_none()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found for this analysis")

    attribs = prediction.feature_attributions or {}
    raw_risk_factors = attribs.get("top_risk_factors", [])
    raw_prot_factors = attribs.get("top_protective_factors", [])

    top_risk = [
        RiskFactorDetail(
            feature_name=f.get("feature_name", ""),
            feature_value=float(f.get("feature_value", 0.0)),
            attribution_score=float(f.get("attribution_score", 0.0)),
            direction=f.get("direction", "RISK_INCREASING"),
            human_explanation=f.get("human_explanation", ""),
        )
        for f in raw_risk_factors
    ]

    top_prot = [
        RiskFactorDetail(
            feature_name=f.get("feature_name", ""),
            feature_value=float(f.get("feature_value", 0.0)),
            attribution_score=float(f.get("attribution_score", 0.0)),
            direction=f.get("direction", "RISK_REDUCING"),
            human_explanation=f.get("human_explanation", ""),
        )
        for f in raw_prot_factors
    ]

    ci_lower = attribs.get("confidence_lower", max(0.0, prediction.risk_score - 0.10))
    ci_upper = attribs.get("confidence_upper", min(1.0, prediction.risk_score + 0.10))

    return RiskPredictionResponse(
        analysis_id=analysis_id,
        risk_score=prediction.risk_score,
        risk_tier=prediction.risk_tier,
        confidence_lower=ci_lower,
        confidence_upper=ci_upper,
        model_version=attribs.get("model_version", "1.0.0"),
        model_name=attribs.get("model_name", "xgboost"),
        top_risk_factors=top_risk,
        top_protective_factors=top_prot,
        calibrated_probability=prediction.calibrated_probability,
    )


@router.get(
    "/{analysis_id}/dependencies",
    response_model=DependencyGraphResponse,
    summary="Get Dependency Graph Nodes and Edges",
)
async def get_analysis_dependencies(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> DependencyGraphResponse:
    stmt = select(Analysis).where(Analysis.id == analysis_id)
    analysis = (await db.execute(stmt)).scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    features_data = analysis.features or {}
    dep_data = analysis.dependency_graph or features_data.get("dependencies", {})

    nodes_raw = dep_data.get("nodes", [])
    edges_raw = dep_data.get("edges", [])

    nodes = [
        GraphNode(
            id=n.get("id", str(i)),
            label=n.get("label", n.get("id", f"node_{i}")),
            node_type=n.get("node_type", "function"),
            file_path=n.get("file_path", ""),
            is_modified=bool(n.get("is_modified", False)),
            is_affected=bool(n.get("is_affected", False)),
            betweenness_centrality=float(n.get("betweenness_centrality", 0.0)),
            fan_in=int(n.get("fan_in", 0)),
            fan_out=int(n.get("fan_out", 0)),
        )
        for i, n in enumerate(nodes_raw)
    ]

    edges = [
        GraphEdge(
            id=e.get("id", f"edge_{i}"),
            source=e.get("source", ""),
            target=e.get("target", ""),
            edge_type=e.get("edge_type", "CALLS"),
        )
        for i, e in enumerate(edges_raw)
    ]

    affected_count = sum(1 for n in nodes if n.is_affected or n.is_modified)

    return DependencyGraphResponse(
        analysis_id=analysis_id,
        nodes=nodes,
        edges=edges,
        total_nodes=len(nodes),
        total_edges=len(edges),
        affected_nodes_count=affected_count,
    )


@router.get(
    "/{analysis_id}/recommended-tests",
    response_model=RecommendedTestsResponse,
    summary="Get Recommended Test Suite",
)
async def get_recommended_tests(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> RecommendedTestsResponse:
    stmt = (
        select(TestRecommendation)
        .where(TestRecommendation.analysis_id == analysis_id)
        .order_by(TestRecommendation.rank)
    )
    result = await db.execute(stmt)
    recs = result.scalars().all()

    # Load analysis for suite analytics
    analysis_stmt = select(Analysis).where(Analysis.id == analysis_id)
    analysis = (await db.execute(analysis_stmt)).scalar_one_or_none()

    features_data = (analysis.features if analysis else {}) or {}
    analytics = features_data.get("test_selection_analytics", {})

    recommended_tests = [
        TestRecommendationResponse(
            rank=r.rank,
            test_identifier=r.test_identifier,
            file_path=r.test_identifier.split("::")[0]
            if "::" in r.test_identifier
            else r.test_identifier,
            test_name=r.test_identifier.split("::")[1]
            if "::" in r.test_identifier
            else r.test_identifier,
            selection_reason=r.selection_reason,
            evidence_level=r.evidence_level,
            estimated_duration_ms=r.estimated_duration_ms,
            priority_score=r.priority_score,
            covered_symbols=[],
        )
        for r in recs
    ]

    total_count = analytics.get("total_suite_count", max(len(recs), 10))
    selected_duration = sum(r.estimated_duration_ms for r in recs)
    total_duration = analytics.get("total_suite_duration_ms", selected_duration * 3)
    time_savings = analytics.get("time_savings_percent", 66.7)
    test_reduct = analytics.get("test_reduction_percent", 65.0)

    return RecommendedTestsResponse(
        analysis_id=analysis_id,
        recommended_tests=recommended_tests,
        total_suite_tests_count=total_count,
        selected_tests_count=len(recommended_tests),
        total_suite_duration_ms=total_duration,
        selected_suite_duration_ms=selected_duration,
        time_savings_percent=time_savings,
        test_reduction_percent=test_reduct,
        budget_limit_ms=60000,
        budget_consumed_ms=selected_duration,
    )


@router.get(
    "/{analysis_id}/report",
    response_model=AnalysisReportResponse,
    summary="Get Full Aggregated Analysis Report",
)
async def get_analysis_report(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnalysisReportResponse:
    overview = await get_analysis(analysis_id, db)
    risk_info = await get_analysis_risk(analysis_id, db)
    tests_info = await get_recommended_tests(analysis_id, db)
    deps_info = await get_analysis_dependencies(analysis_id, db)

    # Build summary markdown
    badge = (
        "🟢"
        if risk_info.risk_tier == "LOW"
        else (
            "🟡"
            if risk_info.risk_tier == "MEDIUM"
            else ("🟠" if risk_info.risk_tier == "HIGH" else "🔴")
        )
    )
    score_pct = int(risk_info.risk_score * 100)

    md_lines = [
        f"## {badge} CodeImpact Pull Request Analysis Report",
        "",
        f"- **Risk Assessment:** **{risk_info.risk_tier}** ({score_pct}% regression probability)",
        f"- **Model:** `{risk_info.model_name}` v`{risk_info.model_version}`",
        f"- **Execution Time:** {overview.execution_duration_ms or 0} ms",
        "",
        "### Top Risk Contributing Factors",
    ]
    for f in risk_info.top_risk_factors:
        md_lines.append(
            f"- **{f.feature_name.replace('_', ' ').capitalize()}** ({f.feature_value:.2f}): {f.human_explanation}"
        )

    md_lines.extend(
        [
            "",
            "### Recommended Test Execution",
            f"- Selected **{tests_info.selected_tests_count}** of **{tests_info.total_suite_tests_count}** tests (**{tests_info.time_savings_percent:.1f}% time saved**).",
        ]
    )

    return AnalysisReportResponse(
        analysis_id=analysis_id,
        pull_request_id=overview.pull_request_id,
        commit_sha=overview.commit_sha,
        status=overview.status,
        risk_score=risk_info.risk_score,
        risk_tier=risk_info.risk_tier,
        summary_markdown="\n".join(md_lines),
        risk=risk_info,
        tests=tests_info,
        dependency_graph_summary={
            "total_nodes": deps_info.total_nodes,
            "total_edges": deps_info.total_edges,
            "affected_nodes_count": deps_info.affected_nodes_count,
        },
    )
