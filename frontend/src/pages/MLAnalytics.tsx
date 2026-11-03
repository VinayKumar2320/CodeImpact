import React from 'react';
import { ArrowLeft, Cpu, CheckCircle, BarChart3, LineChart as ChartIcon } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  LineChart,
  Line,
  CartesianGrid,
} from 'recharts';

interface MLAnalyticsProps {
  onBack: () => void;
}

const COMPARISON_DATA = [
  { model: 'Majority Baseline', pr_auc: 0.133, roc_auc: 0.500, brier: 0.116 },
  { model: 'Change Size Heuristic', pr_auc: 0.172, roc_auc: 0.577, brier: 0.118 },
  { model: 'Logistic Regression', pr_auc: 0.135, roc_auc: 0.505, brier: 0.252 },
  { model: 'Random Forest', pr_auc: 0.147, roc_auc: 0.507, brier: 0.204 },
  { model: 'XGBoost (Selected)', pr_auc: 0.226, roc_auc: 0.577, brier: 0.178 },
];

const CALIBRATION_DATA = [
  { bin: '0 - 20%', predicted: 0.126, actual: 0.137, perfect: 0.10 },
  { bin: '20 - 40%', predicted: 0.271, actual: 0.163, perfect: 0.30 },
  { bin: '40 - 60%', predicted: 0.512, actual: 0.250, perfect: 0.50 },
  { bin: '60 - 80%', predicted: 0.679, actual: 0.200, perfect: 0.70 },
  { bin: '80 - 100%', predicted: 0.828, actual: 0.000, perfect: 0.90 },
];

export const MLAnalytics: React.FC<MLAnalyticsProps> = ({ onBack }) => {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-3">
        <button
          onClick={onBack}
          className="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 transition"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div>
          <div className="flex items-center space-x-2">
            <Cpu className="w-4 h-4 text-brand-400" />
            <h2 className="text-lg font-bold text-white tracking-tight">
              Machine Learning Model & Benchmark Intelligence
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Calibrated supervised models, TreeSHAP local explainability, and cross-repository holdout audits
          </p>
        </div>
      </div>

      {/* Model Spec Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Active Model
          </span>
          <div className="text-xl font-bold text-white">XGBoost Classifier</div>
          <p className="text-[11px] text-slate-400">Scale Pos Weight: 5.49 (imbalance-tuned)</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Model Version
          </span>
          <div className="text-xl font-bold text-brand-400">v1.0.0-calibrated</div>
          <p className="text-[11px] text-slate-400">TreeSHAP explainer fitted</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Historical Dataset
          </span>
          <div className="text-xl font-bold text-white">1,200 PR Records</div>
          <p className="text-[11px] text-slate-400">Chronological 70 / 15 / 15 + Holdout</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Temporal Leakage Audit
          </span>
          <div className="text-xl font-bold text-emerald-400 flex items-center space-x-1.5">
            <CheckCircle className="w-5 h-5" />
            <span>PASSED</span>
          </div>
          <p className="text-[11px] text-slate-400">Zero look-ahead information leakage</p>
        </div>
      </div>

      {/* Model Evaluation Table */}
      <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
        <div>
          <h3 className="font-semibold text-slate-100 text-sm">
            Holdout Evaluation & Generalization Performance
          </h3>
          <p className="text-xs text-slate-400">
            Comparing in-domain chronological test partition against held-out unseen repository (<code className="text-brand-300">pallets/flask</code>)
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="px-4 py-3 font-semibold">Evaluation Split</th>
                <th className="px-4 py-3 font-semibold">Samples</th>
                <th className="px-4 py-3 font-semibold">PR-AUC</th>
                <th className="px-4 py-3 font-semibold">ROC-AUC</th>
                <th className="px-4 py-3 font-semibold">Brier Score</th>
                <th className="px-4 py-3 font-semibold">ECE (Calibration Error)</th>
                <th className="px-4 py-3 font-semibold">F1 Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              <tr className="hover:bg-slate-800/30 transition">
                <td className="px-4 py-3 font-sans font-semibold text-slate-200">
                  In-Domain Chronological Test
                </td>
                <td className="px-4 py-3 text-slate-400">135 (23 pos)</td>
                <td className="px-4 py-3 font-bold text-emerald-400">0.2256</td>
                <td className="px-4 py-3 text-slate-300">0.5765</td>
                <td className="px-4 py-3 text-slate-400">0.1775</td>
                <td className="px-4 py-3 text-slate-400">0.1330</td>
                <td className="px-4 py-3 text-slate-300">0.2857</td>
              </tr>
              <tr className="hover:bg-slate-800/30 transition">
                <td className="px-4 py-3 font-sans font-semibold text-slate-200">
                  Cross-Repository Holdout (<span className="text-brand-400">pallets/flask</span>)
                </td>
                <td className="px-4 py-3 text-slate-400">300 (45 pos)</td>
                <td className="px-4 py-3 font-bold text-emerald-400">0.1743</td>
                <td className="px-4 py-3 text-slate-300">0.5681</td>
                <td className="px-4 py-3 text-slate-400">0.1834</td>
                <td className="px-4 py-3 text-slate-400">0.1751</td>
                <td className="px-4 py-3 text-slate-300">0.1538</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Recharts Visualizations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Model Comparison Bar Chart */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2 text-brand-400">
            <BarChart3 className="w-4 h-4" />
            <h3 className="font-semibold text-slate-100 text-sm">
              Model Comparison (PR-AUC & ROC-AUC)
            </h3>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={COMPARISON_DATA} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <XAxis dataKey="model" stroke="#64748B" fontSize={10} angle={-15} textAnchor="end" />
                <YAxis stroke="#64748B" fontSize={11} domain={[0, 0.7]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0F172A',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    fontSize: '11px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                <Bar dataKey="pr_auc" name="PR-AUC (Target)" fill="#38BDF8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="roc_auc" name="ROC-AUC" fill="#818CF8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Probability Calibration Curve */}
        <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2 text-emerald-400">
            <ChartIcon className="w-4 h-4" />
            <h3 className="font-semibold text-slate-100 text-sm">
              Probability Calibration Curve
            </h3>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={CALIBRATION_DATA} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="bin" stroke="#64748B" fontSize={11} />
                <YAxis stroke="#64748B" fontSize={11} domain={[0, 1]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0F172A',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    fontSize: '11px',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '5px' }} />
                <Line
                  type="monotone"
                  dataKey="actual"
                  name="Observed True Fraction"
                  stroke="#10B981"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="perfect"
                  name="Perfect Calibration"
                  stroke="#64748B"
                  strokeDasharray="4 4"
                  strokeWidth={1.5}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
