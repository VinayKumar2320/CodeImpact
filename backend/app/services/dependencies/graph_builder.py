from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from app.core.logging import get_logger
from app.services.analysis.ast_parser import ModuleASTSummary

logger = get_logger(__name__)


@dataclass
class GraphNode:
    id: str  # e.g. fn:app/auth.py::validate_token
    name: str
    node_type: str  # module, class, function
    file_path: str
    is_modified: bool = False
    is_test: bool = False
    complexity: int = 1
    fan_in: int = 0
    fan_out: int = 0
    centrality: float = 0.0


@dataclass
class GraphEdge:
    source: str
    target: str
    edge_type: str  # CONTAINS, IMPORTS, CALLS
    certainty: str = "CONFIRMED"  # CONFIRMED or INFERRED


@dataclass
class DependencyAnalysisResult:
    total_nodes: int = 0
    total_edges: int = 0
    modified_nodes_count: int = 0
    affected_callers_count: int = 0
    downstream_dependencies_count: int = 0
    mean_betweenness_centrality: float = 0.0
    max_betweenness_centrality: float = 0.0
    mean_fan_in: float = 0.0
    mean_fan_out: float = 0.0
    directly_modified_nodes: list[str] = field(default_factory=list)
    potentially_affected_callers: list[str] = field(default_factory=list)
    downstream_dependencies: list[str] = field(default_factory=list)
    serialized_graph: dict[str, Any] = field(default_factory=dict)


class DependencyGraphBuilder:
    """
    Constructs and analyzes code dependency graphs across repository modules,
    classes, functions, and test cases using NetworkX.
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    def build_graph(
        self,
        module_summaries: list[ModuleASTSummary],
        modified_func_ids: set[str] | None = None,
    ) -> DependencyAnalysisResult:
        self.graph.clear()
        modified_set = modified_func_ids or set()

        # Step 1: Create Module, Class, and Function nodes
        func_lookup: dict[str, str] = {}  # short name / qualified name -> node_id

        for mod in module_summaries:
            mod_id = f"mod:{mod.file_path}"
            is_test = "test" in mod.file_path.lower()
            self.graph.add_node(
                mod_id,
                name=mod.file_path,
                node_type="module",
                file_path=mod.file_path,
                is_modified=False,
                is_test=is_test,
                complexity=1,
            )

            # Classes
            for cls in mod.classes:
                cls_id = f"cls:{mod.file_path}::{cls.name}"
                self.graph.add_node(
                    cls_id,
                    name=cls.name,
                    node_type="class",
                    file_path=mod.file_path,
                    is_modified=False,
                    is_test=is_test,
                    complexity=1,
                )
                self.graph.add_edge(mod_id, cls_id, edge_type="CONTAINS", certainty="CONFIRMED")

            # Functions & Methods
            for fn in mod.functions:
                fn_id = f"fn:{mod.file_path}::{fn.qualified_name}"
                is_mod = (
                    fn_id in modified_set
                    or fn.name in modified_set
                    or fn.qualified_name in modified_set
                )

                self.graph.add_node(
                    fn_id,
                    name=fn.qualified_name,
                    node_type="function",
                    file_path=mod.file_path,
                    is_modified=is_mod,
                    is_test=is_test,
                    complexity=1,
                )

                parent_id = f"cls:{mod.file_path}::{fn.parent_class}" if fn.parent_class else mod_id
                if self.graph.has_node(parent_id):
                    self.graph.add_edge(
                        parent_id, fn_id, edge_type="CONTAINS", certainty="CONFIRMED"
                    )

                func_lookup[fn.name] = fn_id
                func_lookup[fn.qualified_name] = fn_id
                func_lookup[f"{mod.file_path}::{fn.name}"] = fn_id
                func_lookup[f"{mod.file_path}::{fn.qualified_name}"] = fn_id

        # Step 2: Add Module Imports
        for mod in module_summaries:
            src_mod_id = f"mod:{mod.file_path}"
            for imp in mod.imports:
                # Find matching target modules
                for target_mod in module_summaries:
                    if target_mod.file_path != mod.file_path:
                        mod_as_py = imp.module.replace(".", "/")
                        if mod_as_py in target_mod.file_path:
                            target_mod_id = f"mod:{target_mod.file_path}"
                            self.graph.add_edge(
                                src_mod_id,
                                target_mod_id,
                                edge_type="IMPORTS",
                                certainty="CONFIRMED",
                            )

        # Step 3: Add Call Edges
        for mod in module_summaries:
            for call in mod.calls:
                caller_id = f"fn:{mod.file_path}::{call.caller_name}"
                callee_key = call.callee_name.split(".")[-1]

                # Match callee
                if callee_key in func_lookup:
                    callee_id = func_lookup[callee_key]
                    if caller_id != callee_id:  # avoid trivial self-recursion loops
                        self.graph.add_edge(
                            caller_id, callee_id, edge_type="CALLS", certainty="CONFIRMED"
                        )
                else:
                    # Inferred or external call
                    ext_id = f"ext:{call.callee_name}"
                    if not self.graph.has_node(ext_id):
                        self.graph.add_node(
                            ext_id,
                            name=call.callee_name,
                            node_type="external",
                            file_path="",
                            is_modified=False,
                            is_test=False,
                            complexity=1,
                        )
                    self.graph.add_edge(caller_id, ext_id, edge_type="CALLS", certainty="INFERRED")

        # Step 4: Graph Metrics Calculation
        centrality = nx.betweenness_centrality(self.graph) if len(self.graph) > 0 else {}
        for node_id in self.graph.nodes:
            self.graph.nodes[node_id]["centrality"] = round(centrality.get(node_id, 0.0), 4)
            self.graph.nodes[node_id]["fan_in"] = self.graph.in_degree(node_id)
            self.graph.nodes[node_id]["fan_out"] = self.graph.out_degree(node_id)

        # Step 5: Change Impact Mapping
        directly_modified: list[str] = [
            n for n, d in self.graph.nodes(data=True) if d.get("is_modified")
        ]

        affected_callers: set[str] = set()
        downstream_deps: set[str] = set()

        # Call-based subgraph for impact traversal
        call_subgraph = nx.DiGraph(
            [
                (u, v)
                for u, v, d in self.graph.edges(data=True)
                if d.get("edge_type") in ("CALLS", "CONTAINS")
            ]
        )

        for mod_node in directly_modified:
            if mod_node in call_subgraph:
                # Predecessors in call graph = callers of the modified code
                try:
                    callers = nx.ancestors(call_subgraph, mod_node)
                    affected_callers.update(callers)
                except Exception:
                    pass

                # Successors in call graph = downstream callee dependencies
                try:
                    callees = nx.descendants(call_subgraph, mod_node)
                    downstream_deps.update(callees)
                except Exception:
                    pass

        # Summary statistics
        fan_ins = [d.get("fan_in", 0) for _, d in self.graph.nodes(data=True)]
        fan_outs = [d.get("fan_out", 0) for _, d in self.graph.nodes(data=True)]
        centralities = [d.get("centrality", 0.0) for _, d in self.graph.nodes(data=True)]

        mean_fan_in = round(sum(fan_ins) / len(fan_ins), 2) if fan_ins else 0.0
        mean_fan_out = round(sum(fan_outs) / len(fan_outs), 2) if fan_outs else 0.0
        mean_cent = round(sum(centralities) / len(centralities), 4) if centralities else 0.0
        max_cent = max(centralities) if centralities else 0.0

        # Serialize graph representation for PostgreSQL and React Flow
        serialized = self._serialize_graph()

        return DependencyAnalysisResult(
            total_nodes=self.graph.number_of_nodes(),
            total_edges=self.graph.number_of_edges(),
            modified_nodes_count=len(directly_modified),
            affected_callers_count=len(affected_callers),
            downstream_dependencies_count=len(downstream_deps),
            mean_betweenness_centrality=mean_cent,
            max_betweenness_centrality=max_cent,
            mean_fan_in=mean_fan_in,
            mean_fan_out=mean_fan_out,
            directly_modified_nodes=sorted(directly_modified),
            potentially_affected_callers=sorted(affected_callers),
            downstream_dependencies=sorted(downstream_deps),
            serialized_graph=serialized,
        )

    def _serialize_graph(self) -> dict[str, Any]:
        """
        Format graph nodes and edges for React Flow and REST API consumption.
        """
        nodes_out = []
        for n, d in self.graph.nodes(data=True):
            nodes_out.append(
                {
                    "id": n,
                    "label": d.get("name", n),
                    "type": d.get("node_type", "function"),
                    "filePath": d.get("file_path", ""),
                    "isModified": d.get("is_modified", False),
                    "isTest": d.get("is_test", False),
                    "fanIn": d.get("fan_in", 0),
                    "fanOut": d.get("fan_out", 0),
                    "centrality": d.get("centrality", 0.0),
                }
            )

        edges_out = []
        for u, v, d in self.graph.edges(data=True):
            edges_out.append(
                {
                    "id": f"e_{u}_{v}",
                    "source": u,
                    "target": v,
                    "edgeType": d.get("edge_type", "CALLS"),
                    "certainty": d.get("certainty", "CONFIRMED"),
                }
            )

        return {"nodes": nodes_out, "edges": edges_out}


dependency_graph_builder = DependencyGraphBuilder()
