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

const API_BASE = '/api/v1';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`API error (${res.status}): ${errorText || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Repositories
  getRepositories: (): Promise<Repository[]> =>
    fetch(`${API_BASE}/repositories`).then((r) => handleResponse<Repository[]>(r)),

  createRepository: (fullName: string): Promise<Repository> =>
    fetch(`${API_BASE}/repositories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ full_name: fullName, default_branch: 'main' }),
    }).then((r) => handleResponse<Repository>(r)),

  // Pull Requests
  getPullRequests: (repositoryId?: string): Promise<PullRequest[]> => {
    const url = repositoryId
      ? `${API_BASE}/pull-requests?repository_id=${encodeURIComponent(repositoryId)}`
      : `${API_BASE}/pull-requests`;
    return fetch(url).then((r) => handleResponse<PullRequest[]>(r));
  },

  getPullRequestById: (id: string): Promise<PullRequest> =>
    fetch(`${API_BASE}/pull-requests/${encodeURIComponent(id)}`).then((r) =>
      handleResponse<PullRequest>(r)
    ),

  triggerAnalysis: (prId: string): Promise<{ analysis_id: string; status: string }> =>
    fetch(`${API_BASE}/pull-requests/${encodeURIComponent(prId)}/analyze`, {
      method: 'POST',
    }).then((r) => handleResponse<{ analysis_id: string; status: string }>(r)),

  // Analyses
  getAnalysis: (id: string): Promise<AnalysisOverview> =>
    fetch(`${API_BASE}/analyses/${encodeURIComponent(id)}`).then((r) =>
      handleResponse<AnalysisOverview>(r)
    ),

  getAnalysisRisk: (id: string): Promise<RiskPrediction> =>
    fetch(`${API_BASE}/analyses/${encodeURIComponent(id)}/risk`).then((r) =>
      handleResponse<RiskPrediction>(r)
    ),

  getAnalysisDependencies: (id: string): Promise<DependencyGraph> =>
    fetch(`${API_BASE}/analyses/${encodeURIComponent(id)}/dependencies`).then((r) =>
      handleResponse<DependencyGraph>(r)
    ),

  getRecommendedTests: (id: string): Promise<RecommendedTestsPlan> =>
    fetch(`${API_BASE}/analyses/${encodeURIComponent(id)}/recommended-tests`).then((r) =>
      handleResponse<RecommendedTestsPlan>(r)
    ),

  getAnalysisReport: (id: string): Promise<AnalysisReport> =>
    fetch(`${API_BASE}/analyses/${encodeURIComponent(id)}/report`).then((r) =>
      handleResponse<AnalysisReport>(r)
    ),

  // Platform Metrics
  getPlatformMetrics: (): Promise<PlatformMetrics> =>
    fetch(`${API_BASE}/metrics`).then((r) => handleResponse<PlatformMetrics>(r)),
};
