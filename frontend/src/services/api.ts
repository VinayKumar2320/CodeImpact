import {
  AnalysisOverview,
  AnalysisReport,
  DependencyGraph,
  PlatformMetrics,
  PullRequest,
  RecommendedTestsPlan,
  Repository,
  RiskPrediction,
} from '../types';
import {
  DEMO_ANALYSES,
  DEMO_DEPENDENCY_GRAPHS,
  DEMO_PLATFORM_METRICS,
  DEMO_PULL_REQUESTS,
  DEMO_RECOMMENDED_TESTS,
  DEMO_REPOSITORIES,
  DEMO_RISK_PREDICTIONS,
} from './demoData';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const API_BASE = `${BASE_URL}/api/v1`;

let activeDemoMode = import.meta.env.VITE_DEMO_MODE === 'true';

export function isUsingDemoFallback(): boolean {
  return activeDemoMode;
}

async function fetchWithFallback<T>(
  endpoint: string,
  fallback: () => T,
  options?: RequestInit
): Promise<T> {
  if (import.meta.env.VITE_DEMO_MODE === 'true') {
    activeDemoMode = true;
    return fallback();
  }

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, options);
    if (!res.ok) {
      console.warn(`[CodeImpact] API returned ${res.status} for ${endpoint}. Falling back to demo data.`);
      activeDemoMode = true;
      return fallback();
    }
    activeDemoMode = false;
    return (await res.json()) as T;
  } catch (err) {
    console.warn(`[CodeImpact] Backend unreachable at ${API_BASE}${endpoint} (${err}). Falling back to demo data.`);
    activeDemoMode = true;
    return fallback();
  }
}

export const api = {
  // Repositories
  getRepositories: (): Promise<Repository[]> =>
    fetchWithFallback('/repositories', () => DEMO_REPOSITORIES),

  createRepository: (fullName: string): Promise<Repository> =>
    fetchWithFallback(
      '/repositories',
      () => {
        const [owner, name] = fullName.split('/');
        return {
          id: `repo-${Date.now()}`,
          full_name: fullName,
          owner: owner || 'developer',
          name: name || fullName,
          default_branch: 'main',
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
      },
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName, default_branch: 'main' }),
      }
    ),

  // Pull Requests
  getPullRequests: (repositoryId?: string): Promise<PullRequest[]> =>
    fetchWithFallback(
      repositoryId
        ? `/pull-requests?repository_id=${encodeURIComponent(repositoryId)}`
        : '/pull-requests',
      () =>
        repositoryId
          ? DEMO_PULL_REQUESTS.filter((pr) => pr.repository_id === repositoryId)
          : DEMO_PULL_REQUESTS
    ),

  getPullRequestById: (id: string): Promise<PullRequest> =>
    fetchWithFallback(`/pull-requests/${encodeURIComponent(id)}`, () => {
      const match = DEMO_PULL_REQUESTS.find((p) => p.id === id);
      if (match) return match;
      return DEMO_PULL_REQUESTS[0];
    }),

  triggerAnalysis: (prId: string): Promise<{ analysis_id: string; status: string }> =>
    fetchWithFallback(
      `/pull-requests/${encodeURIComponent(prId)}/analyze`,
      () => ({
        analysis_id: 'analysis-103',
        status: 'QUEUED',
      }),
      { method: 'POST' }
    ),

  // Analyses
  getAnalysis: (id: string): Promise<AnalysisOverview> =>
    fetchWithFallback(`/analyses/${encodeURIComponent(id)}`, () => {
      return (
        DEMO_ANALYSES[id] || {
          id,
          pull_request_id: 'pr-103',
          commit_sha: 'c303333333333333333333333333333333333333',
          status: 'COMPLETED',
          analysis_version: '1.0.0',
          execution_duration_ms: 450,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          risk_score: 0.27,
          risk_tier: 'HIGH',
        }
      );
    }),

  getAnalysisRisk: (id: string): Promise<RiskPrediction> =>
    fetchWithFallback(`/analyses/${encodeURIComponent(id)}/risk`, () => {
      return (
        DEMO_RISK_PREDICTIONS[id] ||
        DEMO_RISK_PREDICTIONS['analysis-103']
      );
    }),

  getAnalysisDependencies: (id: string): Promise<DependencyGraph> =>
    fetchWithFallback(`/analyses/${encodeURIComponent(id)}/dependencies`, () => {
      return (
        DEMO_DEPENDENCY_GRAPHS[id] ||
        DEMO_DEPENDENCY_GRAPHS['analysis-103']
      );
    }),

  getRecommendedTests: (id: string): Promise<RecommendedTestsPlan> =>
    fetchWithFallback(`/analyses/${encodeURIComponent(id)}/recommended-tests`, () => {
      return (
        DEMO_RECOMMENDED_TESTS[id] ||
        DEMO_RECOMMENDED_TESTS['analysis-103']
      );
    }),

  getAnalysisReport: (id: string): Promise<AnalysisReport> =>
    fetchWithFallback(`/analyses/${encodeURIComponent(id)}/report`, () => {
      const risk = DEMO_RISK_PREDICTIONS[id] || DEMO_RISK_PREDICTIONS['analysis-103'];
      const tests = DEMO_RECOMMENDED_TESTS[id] || DEMO_RECOMMENDED_TESTS['analysis-103'];
      return {
        analysis_id: id,
        pull_request_id: 'pr-103',
        commit_sha: 'c303333333333333333333333333333333333333',
        status: 'COMPLETED',
        risk_score: risk.risk_score,
        risk_tier: risk.risk_tier,
        summary_markdown: `### 🛡️ CodeImpact Predictive Risk Assessment: **${risk.risk_tier}** (${Math.round(risk.risk_score * 100)}%)\n\nRecommended **${tests.selected_tests_count}** of **${tests.total_suite_tests_count}** tests, saving **${tests.time_savings_percent}%** suite execution time.`,
        risk,
        tests,
        dependency_graph_summary: {
          total_nodes: 9,
          total_edges: 10,
          affected_nodes_count: 5,
        },
      };
    }),

  // Platform Metrics
  getPlatformMetrics: (): Promise<PlatformMetrics> =>
    fetchWithFallback('/metrics', () => DEMO_PLATFORM_METRICS),
};
