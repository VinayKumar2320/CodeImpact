import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  ArrowLeft,
  GitBranch,
  User,
  Hash,
  AlertTriangle,
  ShieldCheck,
  Network,
  ListCheck,
  FileText,
  RefreshCw,
  Cpu,
} from 'lucide-react';
import { api } from '../services/api';
import { AnalysisOverview, PullRequest, RiskPrediction } from '../types';

interface PullRequestAnalysisProps {
  prId: string;
  initialAnalysisId?: string;
  onBack: () => void;
  onNavigateTab: (tab: 'graph' | 'tests' | 'report', analysisId: string) => void;
}

export const PullRequestAnalysis: React.FC<PullRequestAnalysisProps> = ({
  prId,
  initialAnalysisId,
  onBack,
  onNavigateTab,
}) => {
  const [pr, setPr] = useState<PullRequest | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisOverview | null>(null);
  const [risk, setRisk] = useState<RiskPrediction | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [triggering, setTriggering] = useState<boolean>(false);

  const loadAnalysisData = async () => {
    setLoading(true);
    try {
      const prData = await api.getPullRequestById(prId);
      setPr(prData);

      const targetAnalysisId = initialAnalysisId || prData.latest_analysis_id;
      if (targetAnalysisId) {
        const [aData, rData] = await Promise.all([
          api.getAnalysis(targetAnalysisId),
          api.getAnalysisRisk(targetAnalysisId).catch(() => null),
        ]);
        setAnalysis(aData);
        setRisk(rData);
      }
    } catch (err: unknown) {
      console.error('Failed to load analysis details:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAnalysisData();
  }, [prId, initialAnalysisId]);

  const handleTriggerAnalysis = async () => {
    setTriggering(true);
    try {
      await api.triggerAnalysis(prId);
      await loadAnalysisData();
    } catch (err: unknown) {
      console.error('Trigger analysis failed:', err);
    } finally {
      setTriggering(false);
    }
  };

  const tier = risk?.risk_tier || analysis?.risk_tier || 'LOW';
  const scorePercent = risk ? Math.round(risk.risk_score * 100) : 0;

  const tierBadgeColor =
    tier === 'CRITICAL'
      ? 'bg-rose-950 text-rose-400 border-rose-800'
      : tier === 'HIGH'
        ? 'bg-amber-950 text-amber-400 border-amber-800'
        : tier === 'MEDIUM'
          ? 'bg-yellow-950 text-yellow-400 border-yellow-800'
          : 'bg-emerald-950 text-emerald-400 border-emerald-800';

  if (loading) {
    return (
      <div className="py-24 text-center text-slate-400 text-xs flex flex-col items-center justify-center space-y-3">
        <RefreshCw className="w-6 h-6 animate-spin text-brand-400" />
        <p>Loading pull request analysis...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back Button & Title Header */}
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
              <span className="text-xs font-mono text-brand-400">PR #{pr?.pr_number}</span>
              <span className="text-slate-600">•</span>
              <span className="text-xs text-slate-400 font-mono">
                {pr?.head_sha.slice(0, 7)}
              </span>
            </div>
            <h2 className="text-xl font-bold text-white tracking-tight">{pr?.title || 'Loading PR...'}</h2>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {analysis && (
            <div className="flex items-center space-x-2">
              <button
                onClick={() => onNavigateTab('graph', analysis.id)}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 transition"
              >
                <Network className="w-3.5 h-3.5 text-blue-400" />
                <span>Dependency Graph</span>
              </button>
              <button
                onClick={() => onNavigateTab('tests', analysis.id)}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 transition"
              >
                <ListCheck className="w-3.5 h-3.5 text-emerald-400" />
                <span>Recommended Tests</span>
              </button>
              <button
                onClick={() => onNavigateTab('report', analysis.id)}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 transition"
              >
                <FileText className="w-3.5 h-3.5 text-indigo-400" />
                <span>Markdown Report</span>
              </button>
            </div>
          )}

          <button
            onClick={handleTriggerAnalysis}
            disabled={triggering}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-xs font-semibold text-white shadow-md shadow-brand-500/20 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${triggering ? 'animate-spin' : ''}`} />
            <span>{triggering ? 'Analyzing...' : 'Re-Analyze'}</span>
          </button>
        </div>
      </div>

      {/* PR Metadata Banner */}
      <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-wrap items-center gap-6 text-xs text-slate-300">
        <div className="flex items-center space-x-2">
          <User className="w-4 h-4 text-slate-500" />
          <span>Author:</span>
          <span className="font-medium text-white">@{pr?.author}</span>
        </div>
        <div className="flex items-center space-x-2 font-mono">
          <GitBranch className="w-4 h-4 text-slate-500" />
          <span>{pr?.head_ref}</span>
          <span className="text-slate-600">&rarr;</span>
          <span>{pr?.base_ref}</span>
        </div>
        <div className="flex items-center space-x-2 font-mono">
          <Hash className="w-4 h-4 text-slate-500" />
          <span>Commit: {pr?.head_sha.slice(0, 7)}</span>
        </div>
        <div className="flex items-center space-x-2">
          <Cpu className="w-4 h-4 text-slate-500" />
          <span>Analysis Duration: {analysis?.execution_duration_ms ? `${analysis.execution_duration_ms}ms` : '--'}</span>
        </div>
      </div>

      {/* Main Risk Prediction Gauge & SHAP Attributions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Risk Score Gauge Card */}
        <div className="p-6 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-800 flex flex-col items-center justify-center text-center space-y-4">
          <div className="flex items-center space-x-2 text-slate-400">
            <ShieldAlert className="w-4 h-4 text-brand-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider">
              Calibrated Regression Risk
            </h3>
          </div>

          {/* Radial representation */}
          <div className="relative w-40 h-40 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r="42"
                strokeWidth="10"
                stroke="#1E293B"
                fill="transparent"
              />
              <circle
                cx="50"
                cy="50"
                r="42"
                strokeWidth="10"
                stroke={
                  tier === 'CRITICAL'
                    ? '#EF4444'
                    : tier === 'HIGH'
                      ? '#F97316'
                      : tier === 'MEDIUM'
                        ? '#F59E0B'
                        : '#10B981'
                }
                strokeDasharray={264}
                strokeDashoffset={264 - (264 * scorePercent) / 100}
                strokeLinecap="round"
                fill="transparent"
                className="transition-all duration-1000 ease-out"
              />
            </svg>
            <div className="absolute flex flex-col items-center">
              <span className="text-4xl font-extrabold text-white tracking-tight">
                {scorePercent}%
              </span>
              <span className="text-[10px] text-slate-400 uppercase font-semibold">
                Probability
              </span>
            </div>
          </div>

          <div className="space-y-1">
            <span
              className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold border ${tierBadgeColor}`}
            >
              Risk Tier: {tier}
            </span>
            {risk && (
              <p className="text-[11px] text-slate-400">
                Confidence Interval: [{risk.confidence_lower.toFixed(2)}, {risk.confidence_upper.toFixed(2)}]
              </p>
            )}
          </div>

          <p className="text-xs text-slate-400 leading-relaxed max-w-xs pt-2 border-t border-slate-800">
            Predicts likelihood of post-merge regression based on AST complexity deltas, dependency blast radius, and test signals.
          </p>
        </div>

        {/* TreeSHAP Local Explanations */}
        <div className="lg:col-span-2 space-y-6">
          {/* Risk Factors */}
          <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex items-center space-x-2 text-rose-400">
              <AlertTriangle className="w-4 h-4" />
              <h3 className="font-semibold text-sm text-slate-100">
                Key Contributing Risk Factors (TreeSHAP)
              </h3>
            </div>

            {risk?.top_risk_factors && risk.top_risk_factors.length > 0 ? (
              <div className="space-y-3">
                {risk.top_risk_factors.map((factor, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-200">
                        {factor.feature_name.replace(/_/g, ' ').toUpperCase()}
                      </span>
                      <span className="font-mono text-rose-400 font-bold">
                        +{factor.attribution_score.toFixed(3)}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {factor.human_explanation}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No significant risk-elevating factors identified.</p>
            )}
          </div>

          {/* Protective Factors */}
          <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex items-center space-x-2 text-emerald-400">
              <ShieldCheck className="w-4 h-4" />
              <h3 className="font-semibold text-sm text-slate-100">
                Protective Mitigations & Defenses
              </h3>
            </div>

            {risk?.top_protective_factors && risk.top_protective_factors.length > 0 ? (
              <div className="space-y-3">
                {risk.top_protective_factors.map((factor, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-200">
                        {factor.feature_name.replace(/_/g, ' ').toUpperCase()}
                      </span>
                      <span className="font-mono text-emerald-400 font-bold">
                        {factor.attribution_score.toFixed(3)}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {factor.human_explanation}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No specific risk-reducing mitigations recorded.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
