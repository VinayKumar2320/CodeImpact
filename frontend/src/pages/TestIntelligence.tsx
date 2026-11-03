import React, { useState, useEffect } from 'react';
import { ArrowLeft, ListCheck, Copy, Check } from 'lucide-react';
import { api } from '../services/api';
import { RecommendedTestsPlan } from '../types';

interface TestIntelligenceProps {
  analysisId: string;
  onBack: () => void;
}

export const TestIntelligence: React.FC<TestIntelligenceProps> = ({
  analysisId,
  onBack,
}) => {
  const [plan, setPlan] = useState<RecommendedTestsPlan | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    setLoading(true);
    api
      .getRecommendedTests(analysisId)
      .then(setPlan)
      .catch((err) => console.error('Failed to load recommended tests:', err))
      .finally(() => setLoading(false));
  }, [analysisId]);

  const handleCopyCommand = () => {
    if (!plan || plan.recommended_tests.length === 0) return;
    const testIds = plan.recommended_tests.map((t) => t.test_identifier).join(' ');
    const command = `pytest ${testIds}`;
    navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const budgetUsedPct = plan
    ? Math.min(100, Math.round((plan.budget_consumed_ms / plan.budget_limit_ms) * 100))
    : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 transition"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <ListCheck className="w-4 h-4 text-emerald-400" />
              <h2 className="text-lg font-bold text-white tracking-tight">
                Intelligent Test Selection Suite
              </h2>
            </div>
            <p className="text-xs text-slate-400">
              Budgeted greedy marginal coverage maximizing defect detection under execution constraints
            </p>
          </div>
        </div>

        <button
          onClick={handleCopyCommand}
          disabled={!plan || plan.recommended_tests.length === 0}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white shadow-md shadow-emerald-500/20 transition disabled:opacity-50"
        >
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? 'Command Copied!' : 'Copy Pytest Command'}</span>
        </button>
      </div>

      {/* KPI & Budget Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Time Savings
          </span>
          <div className="text-2xl font-bold text-emerald-400">
            {plan ? `${plan.time_savings_percent}%` : '--'}
          </div>
          <p className="text-[11px] text-slate-400">
            {plan ? `${(plan.selected_suite_duration_ms / 1000).toFixed(1)}s` : '--'} vs{' '}
            {plan ? `${(plan.total_suite_duration_ms / 1000).toFixed(1)}s` : '--'} full suite
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Suite Reduction
          </span>
          <div className="text-2xl font-bold text-white">
            {plan ? `${plan.test_reduction_percent}%` : '--'}
          </div>
          <p className="text-[11px] text-slate-400">
            {plan?.selected_tests_count} of {plan?.total_suite_tests_count} tests selected
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2 lg:col-span-2 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400 font-semibold">Execution Time Budget</span>
            <span className="font-mono text-slate-300">
              {plan ? (plan.budget_consumed_ms / 1000).toFixed(1) : 0}s /{' '}
              {plan ? (plan.budget_limit_ms / 1000).toFixed(0) : 60}s limit ({budgetUsedPct}%)
            </span>
          </div>
          <div className="w-full bg-slate-950 rounded-full h-2.5 overflow-hidden border border-slate-800">
            <div
              className={`h-full transition-all duration-500 ${
                budgetUsedPct > 90 ? 'bg-amber-500' : 'bg-emerald-500'
              }`}
              style={{ width: `${budgetUsedPct}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-500">
            Greedy optimizer strictly respects CI execution threshold.
          </p>
        </div>
      </div>

      {/* Recommended Tests Table */}
      <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-slate-100 text-sm">Recommended Test Cases (Ranked)</h3>
            <p className="text-xs text-slate-400">
              Ordered by marginal coverage of changed symbols, failure history, and execution cost
            </p>
          </div>
          <span className="text-xs text-slate-500">
            {plan?.recommended_tests.length || 0} tests selected
          </span>
        </div>

        {loading ? (
          <div className="py-12 text-center text-slate-500 text-xs">Optimizing test selection...</div>
        ) : !plan || plan.recommended_tests.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-xs">
            No tests mapped for this pull request change.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold">Rank</th>
                  <th className="px-4 py-3 font-semibold">Test Identifier</th>
                  <th className="px-4 py-3 font-semibold">Evidence Level</th>
                  <th className="px-4 py-3 font-semibold">Est. Duration</th>
                  <th className="px-4 py-3 font-semibold">Selection Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {plan.recommended_tests.map((test) => {
                  const ev = test.evidence_level;
                  const evBadge =
                    ev === 'EVIDENCE_DYNAMIC_COVERAGE'
                      ? 'bg-blue-950 text-blue-400 border-blue-800'
                      : ev === 'EVIDENCE_STATIC_CALL_GRAPH'
                        ? 'bg-indigo-950 text-indigo-400 border-indigo-800'
                        : 'bg-slate-800 text-slate-300 border-slate-700';

                  return (
                    <tr key={test.rank} className="hover:bg-slate-800/30 transition">
                      <td className="px-4 py-3 font-bold text-brand-400">#{test.rank}</td>
                      <td className="px-4 py-3 font-medium text-slate-200">
                        {test.test_identifier}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold border ${evBadge}`}
                        >
                          {ev.replace('EVIDENCE_', '')}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-400">{test.estimated_duration_ms}ms</td>
                      <td className="px-4 py-3 font-sans text-slate-300 text-xs max-w-sm">
                        {test.selection_reason}
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
