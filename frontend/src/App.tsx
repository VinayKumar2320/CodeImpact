import { useState, useEffect } from 'react'
import { Activity, GitPullRequest, ShieldAlert, Cpu, CheckCircle2, RefreshCw } from 'lucide-react'

export default function App() {
  const [healthStatus, setHealthStatus] = useState<{ status: string; database?: string; redis?: string } | null>(null)
  const [loading, setLoading] = useState<boolean>(true)

  const checkHealth = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/v1/health')
      if (res.ok) {
        const data = await res.json()
        setHealthStatus(data)
      } else {
        setHealthStatus({ status: 'degraded' })
      }
    } catch {
      setHealthStatus({ status: 'offline' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    checkHealth()
  }, [])

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur px-6 py-4 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center space-x-3">
          <div className="bg-brand-500/20 p-2 rounded-lg border border-brand-500/40">
            <ShieldAlert className="w-6 h-6 text-brand-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-blue-400 via-sky-300 to-indigo-300 bg-clip-text text-transparent">
              CodeImpact
            </h1>
            <p className="text-xs text-slate-400 font-medium">Predictive Software Change Risk Analyzer</p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <button
            onClick={checkHealth}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-xs font-medium border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-brand-400' : 'text-slate-400'}`} />
            <span>Health Status: {healthStatus?.status ?? (loading ? 'Checking...' : 'Unknown')}</span>
          </button>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">
            v0.1.0-alpha
          </span>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Hero Section */}
        <div className="p-8 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900/80 to-slate-950 border border-slate-800 shadow-xl relative overflow-hidden">
          <div className="relative z-10 max-w-3xl space-y-3">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-brand-500/10 border border-brand-500/30 text-brand-300 text-xs font-semibold">
              <Cpu className="w-3.5 h-3.5" />
              <span>AST-Driven Impact • ML Risk Prediction • Budgeted Test Selection</span>
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight text-white">
              Shift-Left Change Intelligence for Modern Pull Requests
            </h2>
            <p className="text-slate-300 text-sm leading-relaxed">
              CodeImpact analyzes GitHub pull requests before merge, reconstructing full AST call hierarchies,
              evaluating cyclomatic complexity deltas, predicting post-merge regression likelihood, and selecting
              the minimal high-value test suite.
            </p>
          </div>
        </div>

        {/* System Architecture Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center border border-blue-500/30 text-blue-400">
              <GitPullRequest className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-100">1. AST & Dependency Analysis</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Tree-sitter mapping parses syntax nodes, extracts modified function boundaries, and reconstructs caller/callee directed graphs using NetworkX.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center border border-amber-500/30 text-amber-400">
              <Activity className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-100">2. Supervised Risk Prediction</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              XGBoost and Random Forest models evaluate complexity delta, historical churn, and graph centrality with SHAP explainability.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/30 text-emerald-400">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-100">3. Budgeted Test Selection</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Greedy marginal risk-weighted coverage optimizer recommends high-value tests under developer execution budgets.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 px-6 py-4 text-center text-xs text-slate-500">
        CodeImpact — Production-Grade Predictive Software Change Risk Analyzer
      </footer>
    </div>
  )
}
