import React, { useState, useEffect, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { ArrowLeft, Network, Info } from 'lucide-react';
import { api } from '../services/api';
import { DependencyGraph, GraphNodeData } from '../types';

interface ChangeImpactGraphProps {
  analysisId: string;
  onBack: () => void;
}

export const ChangeImpactGraph: React.FC<ChangeImpactGraphProps> = ({
  analysisId,
  onBack,
}) => {
  const [graphData, setGraphData] = useState<DependencyGraph | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedNode, setSelectedNode] = useState<GraphNodeData | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .getAnalysisDependencies(analysisId)
      .then((data) => {
        setGraphData(data);
        if (data.nodes.length > 0) {
          const mod = data.nodes.find((n) => n.is_modified) || data.nodes[0];
          setSelectedNode(mod);
        }
      })
      .catch((err) => console.error('Failed to load dependency graph:', err))
      .finally(() => setLoading(false));
  }, [analysisId]);

  // Convert API nodes and edges into React Flow format with layout coordinates
  const { initialNodes, initialEdges } = useMemo(() => {
    if (!graphData || graphData.nodes.length === 0) {
      return { initialNodes: [], initialEdges: [] };
    }

    const cols = Math.ceil(Math.sqrt(graphData.nodes.length));
    const nodes: Node[] = graphData.nodes.map((n, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);

      const isMod = n.is_modified;
      const isAff = n.is_affected;

      const bgColor = isMod
        ? '#7F1D1D' // red-900
        : isAff
          ? '#7C2D12' // orange-900
          : '#1E293B'; // slate-800

      const borderColor = isMod
        ? '#EF4444' // red-500
        : isAff
          ? '#F97316' // orange-500
          : '#475569'; // slate-600

      return {
        id: n.id,
        position: { x: col * 260 + 60, y: row * 160 + 60 },
        data: { ...n, label: n.label },
        style: {
          background: bgColor,
          borderColor: borderColor,
          borderWidth: isMod || isAff ? '2px' : '1px',
          color: '#F8FAFC',
          borderRadius: '8px',
          padding: '10px 14px',
          fontSize: '12px',
          fontWeight: 600,
          boxShadow: isMod
            ? '0 0 15px rgba(239, 68, 68, 0.4)'
            : isAff
              ? '0 0 15px rgba(249, 115, 22, 0.3)'
              : 'none',
        },
      };
    });

    const edges: Edge[] = graphData.edges.map((e, idx) => {
      const isCall = e.edge_type === 'CALLS';
      return {
        id: e.id || `e-${idx}`,
        source: e.source,
        target: e.target,
        animated: isCall,
        label: e.edge_type,
        labelStyle: { fill: '#94A3B8', fontSize: 10, fontWeight: 500 },
        style: {
          stroke: isCall ? '#38BDF8' : '#64748B',
          strokeWidth: 1.5,
          strokeDasharray: e.edge_type === 'IMPORTS' ? '5,5' : undefined,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isCall ? '#38BDF8' : '#64748B',
          width: 15,
          height: 15,
        },
      };
    });

    return { initialNodes: nodes, initialEdges: edges };
  }, [graphData]);

  return (
    <div className="space-y-4 h-[calc(100vh-140px)] flex flex-col">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 transition"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <Network className="w-4 h-4 text-blue-400" />
              <h2 className="text-lg font-bold text-white tracking-tight">
                Change Impact Dependency Graph
              </h2>
            </div>
            <p className="text-xs text-slate-400">
              Interactive static call & import graph analyzing blast radius of modified symbols
            </p>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center space-x-4 text-xs">
          <div className="flex items-center space-x-1.5">
            <span className="w-3 h-3 rounded-full bg-rose-500 shadow-sm shadow-rose-500/50" />
            <span className="text-slate-300">Modified Symbol</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-3 h-3 rounded-full bg-orange-500 shadow-sm shadow-orange-500/50" />
            <span className="text-slate-300">Affected Caller</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-3 h-3 rounded-full bg-slate-700" />
            <span className="text-slate-400">Dependency</span>
          </div>
        </div>
      </div>

      {/* Main Flow Canvas with Inspector Drawer */}
      <div className="flex-1 rounded-2xl border border-slate-800 bg-slate-950 overflow-hidden relative flex">
        <div className="flex-1 h-full">
          {initialNodes.length > 0 ? (
            <ReactFlow
              nodes={initialNodes}
              edges={initialEdges}
              onNodeClick={(_, node) => {
                const nodeData = graphData?.nodes.find((n) => n.id === node.id);
                if (nodeData) setSelectedNode(nodeData);
              }}
              fitView
            >
              <Background color="#1E293B" gap={20} size={1} />
              <Controls className="bg-slate-900 border-slate-800 text-white fill-white" />
              <MiniMap
                nodeColor={(n) => {
                  if (n.style?.background) return n.style.background as string;
                  return '#334155';
                }}
                className="bg-slate-950 border border-slate-800 rounded-lg"
              />
            </ReactFlow>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-500 text-xs">
              {loading ? 'Synthesizing Dependency Graph...' : 'No graph nodes extracted for this change.'}
            </div>
          )}
        </div>

        {/* Selected Node Inspector Drawer */}
        {selectedNode && (
          <div className="w-80 border-l border-slate-800 bg-slate-900/90 backdrop-blur p-4 space-y-4 overflow-y-auto z-10">
            <div className="flex items-center space-x-2 text-brand-400 border-b border-slate-800 pb-3">
              <Info className="w-4 h-4" />
              <h3 className="font-semibold text-xs uppercase tracking-wider text-slate-200">
                Symbol Inspector
              </h3>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="text-slate-500 block text-[11px]">Symbol Identifier</span>
                <span className="font-mono font-bold text-white text-xs break-all">
                  {selectedNode.label}
                </span>
              </div>

              <div>
                <span className="text-slate-500 block text-[11px]">File Location</span>
                <span className="font-mono text-slate-300 text-xs break-all">
                  {selectedNode.file_path || 'unknown'}
                </span>
              </div>

              <div>
                <span className="text-slate-500 block text-[11px]">Node Type</span>
                <span className="inline-block mt-0.5 px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[11px]">
                  {selectedNode.node_type}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800">
                <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                  <span className="text-slate-500 block text-[10px]">Betweenness</span>
                  <span className="font-mono font-bold text-white text-xs">
                    {selectedNode.betweenness_centrality.toFixed(4)}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                  <span className="text-slate-500 block text-[10px]">Fan-In / Fan-Out</span>
                  <span className="font-mono font-bold text-white text-xs">
                    {selectedNode.fan_in} / {selectedNode.fan_out}
                  </span>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                <span className="text-slate-400 font-semibold block text-[11px]">
                  Change Impact Status
                </span>
                {selectedNode.is_modified ? (
                  <p className="text-rose-400 text-[11px] leading-relaxed">
                    Directly modified in pull request diff. Re-indexing AST syntax trees.
                  </p>
                ) : selectedNode.is_affected ? (
                  <p className="text-orange-400 text-[11px] leading-relaxed">
                    Potentially affected caller transitively reachable from modified symbols.
                  </p>
                ) : (
                  <p className="text-slate-400 text-[11px] leading-relaxed">
                    Upstream/downstream stable dependency.
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
