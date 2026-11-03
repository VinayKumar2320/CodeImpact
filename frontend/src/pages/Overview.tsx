import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  GitPullRequest,
  Clock,
  Cpu,
  ArrowUpRight,
  Plus,
  RefreshCw,
  FolderGit2,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { api } from '../services/api';
import { PlatformMetrics, PullRequest, Repository } from '../types';

interface OverviewProps {
  onSelectPR: (prId: string, analysisId?: string) => void;
  onNavigate: (page: string) => void;
}

const TIER_COLORS: Record<string, string> = {
  LOW: '#10B981', // emerald-500
  MEDIUM: '#F59E0B', // amber-500
  HIGH: '#F97316', // orange-500
  CRITICAL: '#EF4444', // red-500
};

export const Overview: React.FC<OverviewProps> = ({ onSelectPR, onNavigate }) => {
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null);
  const [pullRequests, setPullRequests] = useState<PullRequest[]>([]);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [newRepoName, setNewRepoName] = useState<string>('');
  const [registering, setRegistering] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>('');

  const loadData = async () => {
    setLoading(true);
    try {
      const [m, prs, repos] = await Promise.all([
        api.getPlatformMetrics().catch(() => null),
        api.getPullRequests().catch(() => []),
        api.getRepositories().catch(() => []),
      ]);
      setMetrics(m);
      setPullRequests(prs);
      setRepositories(repos);
    } catch (err: unknown) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRegisterRepo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRepoName.trim()) return;
    setRegistering(true);
    setErrorMsg('');
    try {
      await api.createRepository(newRepoName.trim());
      setNewRepoName('');
      await loadData();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to register repository');
    } finally {
      setRegistering(false);
    }
  };

  const chartData = metrics
    ? Object.entries(metrics.risk_tier_distribution).map(([tier, count]) => ({
        tier,
        count,
        color: TIER_COLORS[tier] || '#64748B',
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Top Bar Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">Platform Dashboard</h2>
          <p className="text-xs text-slate-400">
            Real-time PR change risk prediction and automated test selection intelligence
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-brand-400' : ''}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => onNavigate('ml-analytics')}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-xs font-semibold text-white shadow-lg shadow-brand-500/20 transition"
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>Model Analytics</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Repositories</span>
            <FolderGit2 className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {metrics?.total_repositories ?? repositories.length}
          </div>
          <p className="text-xs text-slate-500">Active monitored repositories</p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Pull Requests</span>
            <GitPullRequest className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {metrics?.total_pull_requests ?? pullRequests.length}
          </div>
          <p className="text-xs text-slate-500">
            {metrics?.completed_analyses ?? 0} analyses executed
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Average Risk</span>
            <ShieldAlert className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {metrics ? `${Math.round(metrics.average_risk_score * 100)}%` : '--'}
          </div>
          <p className="text-xs text-slate-500">Calibrated regression probability</p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Test Time Saved</span>
            <Clock className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400">
            {metrics ? `${metrics.total_test_time_saved_hours}h` : '0h'}
          </div>
          <p className="text-xs text-slate-500">
            {metrics ? `${metrics.average_test_time_savings_percent}%` : '74%'} suite reduction
          </p>
        </div>
      </div>

      {/* Charts & Quick Registration */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Risk Distribution Chart */}
        <div className="lg:col-span-2 p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-slate-100 text-sm">
                Risk Tier Distribution (Post-Merge Regressions)
              </h3>
              <p className="text-xs text-slate-400">
                Categorized by calibrated model probability
              </p>
            </div>
            <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
              Model: {metrics?.active_model_name ?? 'xgboost'} v
              {metrics?.active_model_version ?? '1.0.0'}
            </span>
          </div>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="tier" stroke="#64748B" fontSize={12} tickLine={false} />
                <YAxis stroke="#64748B" fontSize={12} tickLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0F172A',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Register Repository Card */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 text-brand-400">
              <FolderGit2 className="w-4 h-4" />
              <h3 className="font-semibold text-slate-100 text-sm">Register Repository</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Connect a GitHub repository to listen for pull request webhooks and calculate risk metrics.
            </p>
            <form onSubmit={handleRegisterRepo} className="space-y-3 pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Repository Full Name (owner/repo)
                </label>
                <input
                  type="text"
                  placeholder="tiangolo/fastapi"
                  value={newRepoName}
                  onChange={(e) => setNewRepoName(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-lg bg-slate-950 border border-slate-700 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-brand-500"
                />
              </div>
              {errorMsg && <p className="text-xs text-rose-400">{errorMsg}</p>}
              <button
                type="submit"
                disabled={registering}
                className="w-full flex items-center justify-center space-x-1.5 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-slate-700 transition"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>{registering ? 'Registering...' : 'Add Repository'}</span>
              </button>
            </form>
          </div>

          <div className="pt-3 border-t border-slate-800/80">
            <span className="text-[11px] text-slate-500">
              {repositories.length} repository registered in database
            </span>
          </div>
        </div>
      </div>

      {/* Pull Requests Feed */}
      <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-slate-100 text-sm">Recent Pull Requests</h3>
            <p className="text-xs text-slate-400">
              Click a pull request to inspect AST impact, dependency graph, and recommended tests
            </p>
          </div>
          <span className="text-xs text-slate-500">{pullRequests.length} total pull requests</span>
        </div>

        {pullRequests.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-xs space-y-2">
            <GitPullRequest className="w-8 h-8 mx-auto text-slate-600" />
            <p>No pull requests analyzed yet.</p>
            <p className="text-[11px] text-slate-600">
              Run <code className="bg-slate-800 px-1.5 py-0.5 rounded">python scripts/bootstrap_demo.py</code> or trigger a webhook.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold">PR</th>
                  <th className="px-4 py-3 font-semibold">Title</th>
                  <th className="px-4 py-3 font-semibold">Author</th>
                  <th className="px-4 py-3 font-semibold">Branches</th>
                  <th className="px-4 py-3 font-semibold">Risk Assessment</th>
                  <th className="px-4 py-3 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {pullRequests.map((pr) => {
                  const tier = pr.latest_risk_tier || 'LOW';
                  const tierBg =
                    tier === 'CRITICAL'
                      ? 'bg-rose-950 text-rose-400 border-rose-800'
                      : tier === 'HIGH'
                        ? 'bg-amber-950 text-amber-400 border-amber-800'
                        : tier === 'MEDIUM'
                          ? 'bg-yellow-950 text-yellow-400 border-yellow-800'
                          : 'bg-emerald-950 text-emerald-400 border-emerald-800';

                  return (
                    <tr
                      key={pr.id}
                      onClick={() => onSelectPR(pr.id, pr.latest_analysis_id || undefined)}
                      className="hover:bg-slate-800/40 cursor-pointer transition"
                    >
                      <td className="px-4 py-3 font-mono font-medium text-brand-400">
                        #{pr.pr_number}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-200 max-w-xs truncate">
                        {pr.title}
                      </td>
                      <td className="px-4 py-3 text-slate-400">@{pr.author}</td>
                      <td className="px-4 py-3 font-mono text-[11px] text-slate-400">
                        {pr.head_ref} &rarr; {pr.base_ref}
                      </td>
                      <td className="px-4 py-3">
                        {pr.latest_analysis_id ? (
                          <div className="flex items-center space-x-2">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${tierBg}`}
                            >
                              {tier}
                            </span>
                            {pr.latest_risk_score !== undefined && pr.latest_risk_score !== null && (
                              <span className="text-slate-400 text-[11px]">
                                {Math.round(pr.latest_risk_score * 100)}%
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-500 italic text-[11px]">Pending Analysis</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectPR(pr.id, pr.latest_analysis_id || undefined);
                          }}
                          className="inline-flex items-center space-x-1 text-brand-400 hover:text-brand-300 font-semibold transition"
                        >
                          <span>Inspect</span>
                          <ArrowUpRight className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
