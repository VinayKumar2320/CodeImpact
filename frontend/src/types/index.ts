export type RiskTier = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface Repository {
  id: string;
  full_name: string;
  owner: string;
  name: string;
  default_branch: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PullRequest {
  id: string;
  repository_id: string;
  pr_number: number;
  title: string;
  author: string;
  base_ref: string;
  head_ref: string;
  base_sha: string;
  head_sha: string;
  state: string;
  created_at: string;
  updated_at: string;
  latest_analysis_id?: string | null;
  latest_risk_tier?: RiskTier | null;
  latest_risk_score?: number | null;
}

export interface AnalysisOverview {
  id: string;
  pull_request_id: string;
  commit_sha: string;
  status: string;
  analysis_version: string;
  execution_duration_ms?: number | null;
  created_at: string;
  updated_at: string;
  risk_score?: number | null;
  risk_tier?: RiskTier | null;
}

export interface RiskFactor {
  feature_name: string;
  feature_value: number;
  attribution_score: number;
  direction: 'RISK_INCREASING' | 'RISK_REDUCING';
  human_explanation: string;
}

export interface RiskPrediction {
  analysis_id: string;
  risk_score: number;
  risk_tier: RiskTier;
  confidence_lower: number;
  confidence_upper: number;
  model_version: string;
  model_name: string;
  top_risk_factors: RiskFactor[];
  top_protective_factors: RiskFactor[];
  calibrated_probability?: number | null;
}

export interface GraphNodeData {
  id: string;
  label: string;
  node_type: string;
  file_path: string;
  is_modified: boolean;
  is_affected: boolean;
  betweenness_centrality: number;
  fan_in: number;
  fan_out: number;
}

export interface GraphEdgeData {
  id: string;
  source: string;
  target: string;
  edge_type: string;
}

export interface DependencyGraph {
  analysis_id: string;
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  total_nodes: number;
  total_edges: number;
  affected_nodes_count: number;
}

export interface RecommendedTest {
  rank: number;
  test_identifier: string;
  file_path: string;
  test_name: string;
  selection_reason: string;
  evidence_level: string;
  estimated_duration_ms: number;
  priority_score: number;
  covered_symbols: string[];
}

export interface RecommendedTestsPlan {
  analysis_id: string;
  recommended_tests: RecommendedTest[];
  total_suite_tests_count: number;
  selected_tests_count: number;
  total_suite_duration_ms: number;
  selected_suite_duration_ms: number;
  time_savings_percent: number;
  test_reduction_percent: number;
  budget_limit_ms: number;
  budget_consumed_ms: number;
}

export interface AnalysisReport {
  analysis_id: string;
  pull_request_id: string;
  commit_sha: string;
  status: string;
  risk_score: number;
  risk_tier: RiskTier;
  summary_markdown: string;
  risk: RiskPrediction;
  tests: RecommendedTestsPlan;
  dependency_graph_summary: {
    total_nodes: number;
    total_edges: number;
    affected_nodes_count: number;
  };
}

export interface PlatformMetrics {
  total_repositories: number;
  total_pull_requests: number;
  total_analyses: number;
  completed_analyses: number;
  average_risk_score: number;
  risk_tier_distribution: Record<string, number>;
  total_test_time_saved_hours: number;
  average_test_time_savings_percent: number;
  active_model_name: string;
  active_model_version: string;
}
