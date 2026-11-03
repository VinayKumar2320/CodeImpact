import React, { useState, useEffect } from 'react';
import { ArrowLeft, FileText, Copy, Check } from 'lucide-react';
import { api } from '../services/api';
import { AnalysisReport } from '../types';

interface MarkdownReportProps {
  analysisId: string;
  onBack: () => void;
}

export const MarkdownReport: React.FC<MarkdownReportProps> = ({
  analysisId,
  onBack,
}) => {
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    setLoading(true);
    api
      .getAnalysisReport(analysisId)
      .then(setReport)
      .catch((err) => console.error('Failed to load analysis report:', err))
      .finally(() => setLoading(false));
  }, [analysisId]);

  const handleCopyMarkdown = () => {
    if (!report) return;
    navigator.clipboard.writeText(report.summary_markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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
              <FileText className="w-4 h-4 text-indigo-400" />
              <h2 className="text-lg font-bold text-white tracking-tight">
                Analysis Summary & GitHub Check Report
              </h2>
            </div>
            <p className="text-xs text-slate-400">
              Complete formatted Markdown report published as neutral check runs on GitHub pull requests
            </p>
          </div>
        </div>

        <button
          onClick={handleCopyMarkdown}
          disabled={!report}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md shadow-indigo-500/20 transition disabled:opacity-50"
        >
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? 'Markdown Copied!' : 'Copy Markdown'}</span>
        </button>
      </div>

      {/* Markdown Container */}
      <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl">
        {loading ? (
          <div className="py-12 text-center text-slate-500 text-xs">Generating report...</div>
        ) : !report ? (
          <div className="py-12 text-center text-slate-500 text-xs">Report unavailable.</div>
        ) : (
          <div className="prose prose-invert max-w-none text-xs leading-relaxed font-mono whitespace-pre-wrap bg-slate-950 p-6 rounded-xl border border-slate-800 text-slate-300">
            {report.summary_markdown}
          </div>
        )}
      </div>
    </div>
  );
};
