# Feature Engineering & Mathematical Formulations

## 1. Feature Vector Overview
CodeImpact maps each pull request change into a 25-dimensional standardized tabular feature vector $x \in \mathbb{R}^{25}$. Features are partitioned into five categories:
1. **Change Size & Dispersion**
2. **Abstract Syntax Tree (AST) Granular Changes**
3. **Cyclomatic Complexity Deltas**
4. **Dependency Call Graph & Network Centrality**
5. **Historical File Churn & Test Coverage Metrics**

---

## 2. Exhaustive Feature Specifications

### A. Change Size & Dispersion
| Feature Name | Type | Description |
| :--- | :--- | :--- |
| `change_size` | Float | Total modified lines: $L_{\text{added}} + L_{\text{deleted}}$. |
| `lines_added` | Float | Number of added lines across all diff hunks. |
| `lines_deleted` | Float | Number of deleted lines across all diff hunks. |
| `files_changed_count` | Float | Total distinct files altered in the PR. |
| `test_files_changed_count` | Float | Number of changed files matching test path heuristics (e.g. `tests/test_*.py`). |
| `config_files_changed_count`| Float | Number of configuration files altered (`*.yaml`, `*.json`, `*.toml`, `*.ini`). |

### B. AST Syntactical Diff Features
| Feature Name | Type | Description |
| :--- | :--- | :--- |
| `functions_modified_count` | Float | Functions whose line interval intersects an altered diff hunk. |
| `functions_added_count` | Float | Newly declared functions in head revision not present in base. |
| `functions_deleted_count` | Float | Functions present in base revision but absent in head. |
| `classes_modified_count` | Float | Classes with modified methods or class attributes. |
| `public_api_changes_count` | Float | Changes to non-underscore symbols (`def foo()` vs `def _internal()`). |

### C. Cyclomatic Complexity Deltas ($\Delta CC$)
Calculated per function using Radon and AST inspection:
$$CC = E - N + 2P$$
Where $E$ is the number of edges, $N$ is nodes in the control flow graph, and $P$ is connected components.

| Feature Name | Type | Formula / Description |
| :--- | :--- | :--- |
| `average_complexity` | Float | Mean CC across all functions in modified files on head: $\frac{1}{K}\sum CC_k$. |
| `max_complexity` | Float | Maximum single function CC on head revision. |
| `delta_average_complexity`| Float | Net change in mean complexity: $\overline{CC}_{\text{head}} - \overline{CC}_{\text{base}}$. |
| `delta_max_complexity` | Float | Net change in peak complexity: $\max(CC_{\text{head}}) - \max(CC_{\text{base}})$. |
| `modified_high_complexity_count` | Float | Count of modified functions where $CC \ge 10$ (high-risk branch logic). |

### D. Dependency Call Graph & Network Centrality
Reconstructed into a directed graph $G = (V, E)$ via Tree-sitter call and import traversal:

| Feature Name | Type | Formula / Description |
| :--- | :--- | :--- |
| `affected_callers_count` | Float | Number of downstream functions that transitively call modified symbols: $|\text{Callers}(V_{\text{mod}})|$. |
| `downstream_dependencies_count` | Float | Out-degree reachable symbols from modified components: $|\text{Callees}(V_{\text{mod}})|$. |
| `mean_betweenness_centrality` | Float | Mean betweenness centrality of modified nodes: $$C_B(v) = \sum_{s \ne v \ne t} \frac{\sigma_{st}(v)}{\sigma_{st}}$$ |

High betweenness centrality indicates architectural bottleneck components whose modification ripples across multiple subsystems.

### E. Historical File Churn & Test Coverage
| Feature Name | Type | Description |
| :--- | :--- | :--- |
| `mean_change_frequency` | Float | Historical commit count in the last 90 days for modified files. |
| `distinct_contributors_count`| Float | Number of unique commit authors who touched modified files in the last 180 days. |
| `mean_file_age_days` | Float | Time since initial file creation in days. |
| `recent_change_concentration`| Float | Proportion of all file edits occurring in the last 14 days ($C_{14} / C_{90}$). |
| `test_coverage_ratio` | Float | Fraction of modified executable lines covered by existing dynamic test traces: $\frac{|\text{Lines}_{\text{covered}} \cap \text{Lines}_{\text{diff}}|}{|\text{Lines}_{\text{diff}}|}$. |
| `historical_test_failure_frequency` | Float | Historical failure rate of tests covering the modified files over the past 50 CI runs. |

---

## 3. Extraction Pipeline

```python
from app.ml.features.extractor import feature_extractor

# Feature extraction from static analysis results and git history
tabular_vector = feature_extractor.extract(
    static_result=analysis_result,
    git_churn=churn_metrics,
    coverage_data=ci_coverage_payload,
)
```
Default imputation values for missing historical features ensure that initial commits or brand-new files without historical churn degrade safely without raising numerical errors.
