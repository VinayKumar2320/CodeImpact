from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pull_request_id: str
    commit_sha: str
    status: str
    analysis_version: str
    execution_duration_ms: int | None = None
    created_at: datetime
    updated_at: datetime
    risk_score: float | None = None
    risk_tier: str | None = None


class AnalysisFeaturesResponse(BaseModel):
    analysis_id: str
    commit_sha: str
    features: dict[str, Any]


class RiskFactorDetail(BaseModel):
    feature_name: str
    feature_value: float
    attribution_score: float
    direction: str
    human_explanation: str


class RiskPredictionResponse(BaseModel):
    analysis_id: str
    risk_score: float
    risk_tier: str
    confidence_lower: float
    confidence_upper: float
    model_version: str
    model_name: str
    top_risk_factors: list[RiskFactorDetail]
    top_protective_factors: list[RiskFactorDetail]
    calibrated_probability: float | None = None


class GraphNode(BaseModel):
    id: str
    label: str
    node_type: str  # function, class, module
    file_path: str
    is_modified: bool = False
    is_affected: bool = False
    betweenness_centrality: float = 0.0
    fan_in: int = 0
    fan_out: int = 0


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    edge_type: str  # CALLS, IMPORTS, CONTAINS


class DependencyGraphResponse(BaseModel):
    analysis_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_nodes: int
    total_edges: int
    affected_nodes_count: int


class TestRecommendationResponse(BaseModel):
    rank: int
    test_identifier: str
    file_path: str
    test_name: str
    selection_reason: str
    evidence_level: str
    estimated_duration_ms: int
    priority_score: float
    covered_symbols: list[str]


class RecommendedTestsResponse(BaseModel):
    analysis_id: str
    recommended_tests: list[TestRecommendationResponse]
    total_suite_tests_count: int
    selected_tests_count: int
    total_suite_duration_ms: int
    selected_suite_duration_ms: int
    time_savings_percent: float
    test_reduction_percent: float
    budget_limit_ms: int
    budget_consumed_ms: int


class AnalysisReportResponse(BaseModel):
    analysis_id: str
    pull_request_id: str
    commit_sha: str
    status: str
    risk_score: float
    risk_tier: str
    summary_markdown: str
    risk: RiskPredictionResponse
    tests: RecommendedTestsResponse
    dependency_graph_summary: dict[str, Any]
