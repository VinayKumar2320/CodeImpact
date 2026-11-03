import { useState, useEffect } from 'react';
import { ShieldAlert, RefreshCw } from 'lucide-react';
import { Overview } from './pages/Overview';
import { PullRequestAnalysis } from './pages/PullRequestAnalysis';
import { ChangeImpactGraph } from './pages/ChangeImpactGraph';
import { TestIntelligence } from './pages/TestIntelligence';
import { MLAnalytics } from './pages/MLAnalytics';
import { MarkdownReport } from './pages/MarkdownReport';

export default function App() {
  const [currentPage, setCurrentPage] = useState<string>('overview');
  const [selectedPrId, setSelectedPrId] = useState<string | null>(null);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<string | null>(null);

  const [healthStatus, setHealthStatus] = useState<{ status: string } | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);

  const checkHealth = async () => {
    setHealthLoading(true);
    try {
      const res = await fetch('/api/v1/health');
      if (res.ok) {
        const data = await res.json();
        setHealthStatus(data);
      } else {
        setHealthStatus({ status: 'degraded' });
      }
    } catch {
      setHealthStatus({ status: 'offline' });
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  const handleSelectPR = (prId: string, analysisId?: string) => {
    setSelectedPrId(prId);
    setSelectedAnalysisId(analysisId || null);
    setCurrentPage('pr-analysis');
  };

  const handleNavigateTab = (tab: 'graph' | 'tests' | 'report', analysisId: string) => {
    setSelectedAnalysisId(analysisId);
    setCurrentPage(tab);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur px-6 py-3.5 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center space-x-6">
          <div
            onClick={() => setCurrentPage('overview')}
            className="flex items-center space-x-3 cursor-pointer group"
          >
            <div className="bg-brand-500/20 p-2 rounded-lg border border-brand-500/40 group-hover:border-brand-500 transition">
              <ShieldAlert className="w-5 h-5 text-brand-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight bg-gradient-to-r from-blue-400 via-sky-300 to-indigo-300 bg-clip-text text-transparent">
                CodeImpact
              </h1>
              <p className="text-[10px] text-slate-400 font-medium">
                Predictive Software Change Risk Analyzer
              </p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center space-x-1 pl-4 border-l border-slate-800 text-xs">
            <button
              onClick={() => setCurrentPage('overview')}
              className={`px-3 py-1.5 rounded-md font-medium transition ${
                currentPage === 'overview'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              Dashboard
            </button>
            <button
              onClick={() => setCurrentPage('ml-analytics')}
              className={`px-3 py-1.5 rounded-md font-medium transition ${
                currentPage === 'ml-analytics'
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              Model Intelligence
            </button>
          </nav>
        </div>

        {/* Health status & version */}
        <div className="flex items-center space-x-3">
          <button
            onClick={checkHealth}
            className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-[11px] font-medium border border-slate-700 transition"
          >
            <RefreshCw
              className={`w-3 h-3 ${healthLoading ? 'animate-spin text-brand-400' : 'text-slate-400'}`}
            />
            <span>API: {healthStatus?.status ?? (healthLoading ? 'Checking...' : 'Ready')}</span>
          </button>
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">
            v1.0.0
          </span>
        </div>
      </header>

      {/* Main Content Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6">
        {currentPage === 'overview' && (
          <Overview onSelectPR={handleSelectPR} onNavigate={setCurrentPage} />
        )}

        {currentPage === 'pr-analysis' && selectedPrId && (
          <PullRequestAnalysis
            prId={selectedPrId}
            initialAnalysisId={selectedAnalysisId || undefined}
            onBack={() => setCurrentPage('overview')}
            onNavigateTab={handleNavigateTab}
          />
        )}

        {currentPage === 'graph' && selectedAnalysisId && (
          <ChangeImpactGraph
            analysisId={selectedAnalysisId}
            onBack={() => setCurrentPage('pr-analysis')}
          />
        )}

        {currentPage === 'tests' && selectedAnalysisId && (
          <TestIntelligence
            analysisId={selectedAnalysisId}
            onBack={() => setCurrentPage('pr-analysis')}
          />
        )}

        {currentPage === 'report' && selectedAnalysisId && (
          <MarkdownReport
            analysisId={selectedAnalysisId}
            onBack={() => setCurrentPage('pr-analysis')}
          />
        )}

        {currentPage === 'ml-analytics' && (
          <MLAnalytics onBack={() => setCurrentPage('overview')} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 px-6 py-4 text-center text-xs text-slate-500">
        CodeImpact — Predictive Software Change Risk Analyzer & Automated Test Selection
      </footer>
    </div>
  );
}
