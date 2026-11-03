# CodeImpact — Architectural Plan and Phased Execution Roadmap

## 1. Executive Summary & Architectural Vision

**CodeImpact** is a production-oriented developer tools and continuous integration platform designed to evaluate post-merge regression risk and optimize continuous integration test suites for GitHub pull requests. Instead of functioning as a superficial LLM-based code review bot, CodeImpact integrates deterministic static analysis, Abstract Syntax Tree (AST) inspection, code dependency graph reconstruction, historical churn metrics, and a calibrated supervised machine learning model (XGBoost / Random Forest) with TreeSHAP explainability to produce explainable risk predictions and risk-weighted, budgeted test selections.

The system is architected as an asynchronous, event-driven modular monolith:
1. **GitHub Ingestion Layer**: Verifies HMAC-SHA256 signatures, deduplicates deliveries using Redis `SETNX` on delivery IDs, and enqueues pull request analysis jobs.
2. **Analysis & Snapshot Engine**: Fetches git tree snapshots safely without host code execution, computes AST-based syntax differences using Tree-sitter and Python AST, measures cyclomatic complexity (Radon), and maps dependency graphs (NetworkX).
3. **ML Inference & Explainability Layer**: Computes static, churn, complexity, and dependency features; predicts regression probability via versioned XGBoost pipelines; provides TreeSHAP feature contribution breakdowns.
4. **Intelligent Test Selection Engine**: Maps modified symbols to test cases via coverage matrices and dependency call graphs; executes budgeted greedy marginal coverage optimization; provides human-readable explanations and confidence tags.
5. **Presentation & Feedback Layer**: Exposes FastAPI REST endpoints, real-time polling to a React 18 + TypeScript + Tailwind CSS dashboard with interactive dependency graph visualizations (React Flow) and ML evaluation metrics (Recharts), and publishes GitHub Check Runs back to GitHub.

---

## 2. Technical Decisions & Architectural Matrix

| Component | Choice | Rationale & Tradeoffs |
|---|---|---|
| **Architecture** | Modular Monolith + Async Workers | Avoids premature microservice network latency and operational complexity, while enforcing strict domain boundary isolation inside `backend/app/services/` and offloading heavy analysis to worker queues. |
| **Worker Queue** | Redis + RQ (Redis Queue) with direct fallback | Lightweight, reliable, natively Pythonic, uses Redis for job status/locks/retries, and avoids Celery's configuration sprawl while satisfying strict idempotency and timeout controls. |
| **Database & ORM** | PostgreSQL 16 + SQLAlchemy 2.0 (asyncpg & psycopg2) + Alembic | Strong relational consistency, JSONB support for dependency subgraphs and feature vectors, transactional integrity, and battle-tested migration versioning. |
| **Parser / AST Engine**| Tree-sitter (`tree-sitter`, `tree-sitter-python`, `tree-sitter-typescript`) + Python `ast` | Native Tree-sitter provides robust, incremental parsing even on partial or malformed code diffs; standard `ast` provides secondary deep validation for Python. |
| **Dependency Graph** | NetworkX | High-performance graph algorithms (PageRank, betweenness centrality, shortest path, transitive closures) that run in-memory per snapshot analysis. |
| **ML Engine** | Scikit-learn + XGBoost + SHAP + MLflow + Joblib | XGBoost handles tabular software engineering metrics with superior performance, handles missing values gracefully, and integrates with TreeSHAP for fast, exact feature attribution. |
| **Frontend** | React 18 + TypeScript + Vite + Tailwind CSS + TanStack Query + React Flow (`@xyflow/react`) + Recharts | Type-safe, snappy developer experience, fast visual dependency exploration with React Flow, and clean charts with Recharts. |
| **Security Boundary** | Read-only static analysis, untrusted git input isolation, no host execution | Source code is treated as hostile input. Parsing is sandboxed. CI coverage data is ingested from trusted artifacts; no arbitrary code is run on the backend host. |

---

## 3. Phased Implementation Roadmap & Verification Gates

### Phase 1: Project Foundations & Monorepo Architecture [STATUS: COMPLETED ✅]
- **Deliverables**:
  - Monorepo directory structure established (`backend/`, `frontend/`, `scripts/`, `datasets/`, `docs/`, `examples/`, `.github/`).
  - Python 3.12+ configuration with `pyproject.toml`, FastAPI, SQLAlchemy 2.0 async/sync engine, Alembic migrations (`001_initial_schema.py`), Redis queue manager (`TaskQueueManager`), Pydantic v2 settings.
  - React 18 + TypeScript + Vite + Tailwind CSS frontend boilerplate with TanStack Query and Lucide icons.
  - Multi-stage Dockerfiles (`backend/Dockerfile`, `backend/worker.Dockerfile`, `frontend/Dockerfile`) and `docker-compose.yml` orchestrating PostgreSQL 16, Redis 7, Backend, Worker, Frontend.
  - Structured JSON logging (`JSONFormatter`), request correlation IDs (`CorrelationIdMiddleware`), and `/api/v1/health` readiness probe.
  - CI workflow (`.github/workflows/ci.yml`).

### Phase 2: GitHub Integration & Webhook Processing [STATUS: COMPLETED ✅]
- **Deliverables**:
  - `GitHubAuthService`: RS256 JWT generation with 2048-bit key support, installation access token retrieval, in-memory caching.
  - `GitHubClient`: Asynchronous GitHub REST client with automatic exponential backoff, jitter, rate limit retry (403/429), pagination over PR files, raw unified diff fetching, and unified error hierarchy (`GitHubAPIError`).
  - `WebhookHandlerService`: Ingress routing for `pull_request.opened`, `synchronize`, `reopened`, `closed`, and `installation` events; Redis `SETNX` delivery deduplication (24h TTL); automatic invalidation/superseding of outdated analyses when new commits arrive.
  - `RepositorySnapshotService`: Secure diff and content retrieval with strict path sanitization preventing directory traversal, absolute paths, and null-byte injection (`PathTraversalSecurityError`).

### Phase 3: Static Code Analysis & Dependency Engine [STATUS: COMPLETED ✅]
- **Deliverables**:
  - `UnifiedDiffParser`: Full parsing of unified git diffs, hunk line extraction, added/deleted line tracking, and file classification (`test_file`, `config_file`, `doc`, `source`).
  - `PythonASTParser` (Tree-sitter Python): AST extraction for modules, functions, classes, imports, and function calls; diff-to-AST intersection identifying modified, added, and deleted functions and public API modifications.
  - `TypeScriptASTParser` (Tree-sitter TypeScript): Multi-language support extracting classes, exported functions, arrow functions, and method definitions for `.ts` and `.tsx` files.
  - `ComplexityAnalyzer` (Radon + AST): Computes cyclomatic complexity ($CC$), SLOC, nesting depth, parameter counts, $\Delta CC$ between base and head revisions, and high-complexity function counts ($CC \ge 10$).
  - `DependencyGraphBuilder` (NetworkX): Reconstructs directed dependency graphs with `CONTAINS`, `IMPORTS`, and `CALLS` edges; computes fan-in, fan-out, betweenness centrality; maps directly modified nodes to transitive affected callers.
  - `GitChurnAnalyzer`: Computes file-level commit frequency over lookback windows, distinct contributors, file age, and Gini coefficient of change concentration.

### Phase 4: Historical Dataset Collection & Ground Truth Labeling [STATUS: COMPLETED ✅]
- **Deliverables**:
  - `scripts/collect_dataset.py` with GitHub API rate-limit resilience.
  - 1,200 records mined across `fastapi`, `requests`, `httpx`, and `flask` (isolated holdout).
  - Multi-tier regression labeling methodology (Tier 1 explicit reverts & linked issues, Tier 2 subsequent bug-fix PRs within 30 days).
  - Zero look-ahead temporal leakage assertion: $\max(\text{train}) < \min(\text{val}) \le \max(\text{val}) < \min(\text{test})$.
  - Verified manifests in `datasets/train.jsonl` (630), `val.jsonl` (135), `test.jsonl` (135), `cross_repo_test.jsonl` (300), and `datasets/manifest.json`.

### Phase 5: Regression Risk Prediction & ML Engine [STATUS: COMPLETED ✅]
- **Deliverables**:
  - 25-feature tabular vector extractor: change size, cyclomatic complexity delta, graph centrality, churn, and test metrics.
  - Baseline models: Majority class baseline, Change size heuristic baseline, Logistic Regression, Random Forest.
  - Supervised training pipeline (`scripts/train_model.py`): Calibrated XGBoost with isotonic probability calibration and TreeSHAP explainer.
  - Persisted model artifact: `backend/app/ml/models_store/risk_model_v1.joblib` and `model_metadata.json`.
  - Inference service (`RiskPredictor`): Returns calibrated risk probability, risk tier (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), confidence intervals, and top SHAP feature contributions.

### Phase 6: Intelligent Test Selection Engine [STATUS: COMPLETED ✅]
- **Deliverables**:
  - Multi-tier coverage mapping: `EVIDENCE_DYNAMIC_COVERAGE` (weight 1.0), `EVIDENCE_STATIC_CALL_GRAPH` (weight 0.8), `EVIDENCE_DEPENDENCY_HEURISTIC` (weight 0.5).
  - `TestSelectionOptimizer`: Budgeted greedy marginal coverage optimizer maximizing risk-weighted coverage under execution time budget $B$.
  - Benchmark utility (`scripts/benchmark_test_selection.py`): Demonstrates 100% defect recall with 73.7% execution time savings over full suite.

### Phase 7: FastAPI Backend Services & Endpoints [STATUS: COMPLETED ✅]
- **Deliverables**:
  - Full REST API endpoints:
    - `/api/v1/repositories` (list, register, inspect)
    - `/api/v1/pull-requests` (list, detail, by repo)
    - `/api/v1/analyses/{id}` (overview, `/features`, `/risk`, `/dependencies`, `/recommended-tests`, `/report`)
    - `/api/v1/metrics` and `/api/v1/metrics/prometheus` (Prometheus telemetry)
  - `AnalysisOrchestrationService`: End-to-end pipeline coordination.

### Phase 8: React Dashboard & Visualizations [STATUS: COMPLETED ✅]
- **Deliverables**:
  - `Overview.tsx`: Repository KPI cards, average risk scores, test time savings, risk distribution bar charts (Recharts), recent pull request table.
  - `PullRequestAnalysis.tsx`: Radial risk gauge, confidence interval, risk tier badge, TreeSHAP factor attribution waterfall list.
  - `ChangeImpactGraph.tsx`: Interactive React Flow (`@xyflow/react`) directed dependency graph with node inspector detailing in-degree, out-degree, and betweenness centrality.
  - `TestIntelligence.tsx`: Filterable table of recommended tests, execution duration, evidence level, time savings meter, and copyable `pytest` execution command.
  - `MLAnalytics.tsx`: ROC-AUC curves, calibration curves, model comparisons, and cross-repo holdout evaluation.
  - `MarkdownReport.tsx`: Rendered and copyable GitHub Check Run markdown report.

### Phase 9: GitHub Checks & Reporting [STATUS: COMPLETED ✅]
- **Deliverables**:
  - `GitHubCheckRunPublisher`: Formats and publishes informational GitHub Check Runs with collapsible Markdown details, risk assessments, and test execution CLI snippets.
  - Fallback mock publisher for local environments without active GitHub App credentials.

### Phase 10: Security Hardening & Reliability [STATUS: COMPLETED ✅]
- **Deliverables**:
  - Untrusted code non-execution assertion: strict Tree-sitter AST parsing without host code execution.
  - Timing-safe HMAC-SHA256 signature verification (`hmac.compare_digest`).
  - Path traversal fuzzing defense rejecting null bytes, backslashes, and directory escapes.
  - GitHub App token isolation: zero token exposure in database or REST responses.

### Phase 11: End-to-End Testing & Failure Scenarios [STATUS: COMPLETED ✅]
- **Deliverables**:
  - `test_end_to_end_lifecycle.py`: Webhook intake $\to$ deduplication $\to$ static analysis $\to$ ML inference $\to$ test selection $\to$ check run formatting $\to$ supersede on synchronize.
  - `test_failure_scenarios.py`: Extreme feature resilience, zero/tight budget enforcement, corrupted/binary diff resilience.
  - 92 passing automated tests with 0 failures across the test suite.

### Phase 12: Benchmarking & Research Evaluation [STATUS: COMPLETED ✅]
- **Deliverables**:
  - Model evaluation comparing Majority, Change-size heuristic, Logistic Regression, Random Forest, XGBoost in `backend/app/ml/models_store/evaluation_report.json`.
  - Test selection benchmark in `datasets/test_selection_benchmark.json` confirming 100% defect recall and 73.7% execution time reduction.
  - Cross-repo evaluation on `pallets/flask` preserving 98.5% of ROC-AUC ranking capability.

### Phase 13: Containerization & Demo Bootstrapping [STATUS: COMPLETED ✅]
- **Deliverables**:
  - Multi-stage hardened Dockerfiles for backend, worker, and frontend.
  - `docker-compose.yml` orchestrating PostgreSQL 16, Redis 7, Backend, Worker, Frontend.
  - `scripts/bootstrap_demo.py`: One-command utility seeding realistic repositories (`tiangolo/fastapi`, `psf/requests`, `pallets/flask`) and PRs across all four risk tiers (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) with automatic local SQLite fallback.

### Phase 14: Comprehensive Documentation & Plan Completion [STATUS: COMPLETED ✅]
- **Deliverables**:
  - Master `README.md` with system overview, architecture diagram, benchmark tables, and quickstart instructions.
  - Complete engineering guides in `docs/`:
    - `docs/architecture.md`
    - `docs/data_collection.md`
    - `docs/feature_engineering.md`
    - `docs/model_evaluation.md`
    - `docs/test_selection.md`
    - `docs/security.md`
    - `docs/deployment.md`
  - Fully updated and validated `plan.md`.

---

## 4. Final Quality Verification Summary

| Gate | Tool / Command | Result |
| :--- | :--- | :--- |
| **Backend Tests** | `pytest backend/tests/` | **92 / 92 Passed (100%)** |
| **Backend Linting** | `ruff check backend/ scripts/` | **0 Errors** |
| **Backend Formatting** | `ruff format --check backend/ scripts/` | **104 files verified** |
| **Static Type Checking** | `mypy --config-file backend/pyproject.toml backend/app` | **0 Errors across 66 files** |
| **Frontend Unit Tests** | `npm --prefix frontend test` | **2 / 2 Passed (100%)** |
| **Frontend Production Build** | `npm --prefix frontend run build` | **Built successfully without errors** |
| **Demo Bootstrapping** | `python scripts/bootstrap_demo.py` | **4 PRs seeded across LOW, MED, HIGH, CRIT** |
