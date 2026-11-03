# CodeImpact — Architectural Plan and Phased Execution Roadmap

## 1. Executive Summary & Architectural Vision

**CodeImpact** is a production-oriented, developer-infrastructure platform designed to evaluate post-merge regression risk and optimize continuous integration for GitHub pull requests. Instead of functioning as a superficial LLM-based code review bot, CodeImpact integrates deterministic static analysis, Abstract Syntax Tree (AST) inspection, code dependency graph reconstruction, historical churn metrics, and a calibrated supervised machine learning model (XGBoost / Random Forest) to produce explainable risk predictions and risk-weighted, budgeted test selections.

The system is architected as an asynchronous, event-driven modular monolith:
1. **GitHub Ingestion Layer**: Verifies HMAC-SHA256 signatures, deduplicates deliveries using delivery IDs, and enqueues pull request analysis jobs.
2. **Analysis & Snapshot Engine**: Fetches git tree snapshots safely without host code execution, computes AST-based syntax differences using Tree-sitter and Python AST, measures cyclomatic complexity (Radon), and maps dependency graphs (NetworkX).
3. **ML Inference & Explainability Layer**: Computes static, churn, complexity, and dependency features; predicts regression probability via versioned scikit-learn/XGBoost pipelines; provides SHAP feature contribution breakdowns.
4. **Intelligent Test Selection Engine**: Maps modified symbols to test cases via coverage matrices and dependency call graphs; executes budgeted greedy marginal coverage optimization; provides human-readable explanations and confidence tags.
5. **Presentation & Feedback Layer**: Exposes FastAPI REST endpoints, real-time WebSocket/REST polling to a React + TypeScript + Tailwind CSS dashboard with interactive dependency graph visualizations (React Flow) and ML evaluation metrics (Recharts), and publishes GitHub Check Runs back to GitHub.

---

## 2. Technical Decisions & Assumptions

| Component | Choice | Rationale & Tradeoffs |
|---|---|---|
| **Architecture** | Modular Monolith + Async Workers | Avoids premature microservice network latency and operational complexity, while enforcing strict domain boundary isolation inside `backend/app/services/` and offloading heavy analysis to worker queues. |
| **Worker Queue** | Redis + RQ (Redis Queue) with fallback to in-memory/direct async execution for testing | RQ is lightweight, reliable, natively Pythonic, uses Redis for job status/locks/retries, and avoids Celery's configuration sprawl while satisfying strict idempotency and timeout controls. |
| **Database & ORM** | PostgreSQL 16 + SQLAlchemy 2.0 (asyncpg & psycopg2) + Alembic | Strong relational consistency, JSONB support for dependency subgraphs and feature vectors, transactional integrity, and battle-tested migration versioning. |
| **Parser / AST Engine**| Tree-sitter (`tree-sitter`, `tree-sitter-python`, `tree-sitter-typescript`) + Python `ast` | Native Tree-sitter provides robust, incremental parsing even on partial or malformed code diffs; standard `ast` provides secondary deep validation for Python. |
| **Dependency Graph** | NetworkX | High-performance graph algorithms (PageRank, betweenness centrality, shortest path, transitive closures) that run in-memory per snapshot analysis. |
| **ML Engine** | Scikit-learn + XGBoost + SHAP + MLflow | XGBoost handles tabular software engineering metrics with superior performance, handles missing values gracefully, and integrates with TreeSHAP for fast, exact feature attribution. |
| **Frontend** | React 18 + TypeScript + Vite + Tailwind CSS + TanStack Query + React Flow + Recharts | Type-safe, snappy developer experience, fast visual dependency exploration with React Flow, and clean charts with Recharts. |
| **Security Boundary** | Read-only static analysis, untrusted git input isolation, no host execution | Source code is treated as hostile input. Parsing is sandboxed. CI coverage data is ingested from trusted artifacts; no arbitrary code is run on the backend host. |

---

## 3. Critical Technical Risks & Mitigation Strategies

### Risk 1: Regression Labeling Ground Truth & Ambiguity
- **Challenge**: Git commits and pull requests rarely have unambiguous regression labels. Using naive proxies (e.g., commit messages mentioning "fix", or failed CI checks) introduces massive noise and false positives.
- **Mitigation**:
  1. Define a strict multi-tier labeling hierarchy: Tier 1 (confirmed explicit reverts and linked regression bug-fix issues), Tier 2 (subsequent bug-fix PRs modifying identical functions within a 30-day post-merge window), Tier 3 (ambiguous bug fixes excluded from training).
  2. Implement an audit log for label provenance (`label_provenance`, `observation_window_days`).
  3. Cleanly isolate ambiguous samples into an evaluation partition to prevent label noise from degrading model training.

### Risk 2: Test Coverage Mapping & Granularity
- **Challenge**: Standard line coverage reports (e.g. general `.coverage` or summary XML) aggregate lines across all tests combined, destroying the per-test mapping necessary for test selection.
- **Mitigation**:
  1. Leverage `pytest-cov` with `--cov-context=test` (Coverage.py test contexts) or `pytest-json-report` mapping tests to covered dynamic contexts.
  2. Provide a static fallback: Map test function call graphs and import statements to changed code symbols using AST analysis when dynamic per-test coverage matrices are absent.
  3. Mark every recommendation with explicit evidence levels: `EVIDENCE_DYNAMIC_COVERAGE`, `EVIDENCE_STATIC_CALL_GRAPH`, or `EVIDENCE_DEPENDENCY_HEURISTIC`, alerting developers when coverage data is incomplete.

### Risk 3: Dynamic Language Analysis Limitations (Python / TypeScript)
- **Challenge**: Dynamic dispatch, runtime monkey-patching, `getattr()`, dependency injection, and re-exported modules can hide call graph edges from pure static analysis.
- **Mitigation**:
  1. Distinguish between *confirmed* static edges (direct imports and named function invocations) and *inferred/uncertain* edges (dynamic calls, duck-typed references).
  2. Flag uncertain relationships with dashed lines in the dependency graph and expose an uncertainty score in the API.

### Risk 4: Untrusted Code Execution & Worker Isolation
- **Challenge**: Opening pull requests from public repositories could introduce malicious code payloads aimed at compromising the analysis server.
- **Mitigation**:
  1. Never invoke Python `eval()`, `exec()`, or run repository tests directly on the core backend server.
  2. All AST parsing and static inspections use Tree-sitter and Python's AST parser in memory on isolated file blobs.
  3. Git operations are executed with sanitized revision references (`--`, strict SHA validation) to prevent git argument injection.

### Risk 5: Temporal Data Leakage in ML Modeling
- **Challenge**: Random k-fold cross-validation leaks future repository patterns into past predictions, producing unrealistically optimistic metrics that collapse in production.
- **Mitigation**:
  1. Enforce strict temporal train/validation/test splits where train timestamps < validation timestamps < test timestamps.
  2. Implement cross-repository evaluation where held-out target repositories are never seen during training to benchmark cross-project generalization.

---

## 4. Minimal End-to-End Vertical Slice (MVP Milestone)

The minimal viable slice will prove the core end-to-end flow before expanding to extensive modeling:
1. **GitHub Simulation / Webhook Intake**: Securely receive a pull request event payload with HMAC-SHA256 signature verification.
2. **Snapshot Ingestion**: Fetch changed files, base SHA, and head SHA from a sample repository fixture.
3. **AST Static Analysis**: Parse Python files with Tree-sitter/AST to extract changed functions, cyclomatic complexity (Radon), and build a NetworkX dependency graph.
4. **Baseline Risk Scorer**: Compute structured complexity delta, churn, and dependency centrality metrics; produce an interpretable heuristic baseline score with explanation vectors.
5. **Test Selection**: Identify test cases covering modified functions using test-context coverage and call graphs; optimize selection against a specified runtime budget.
6. **Persistence**: Store Repository, PullRequest, Analysis, Prediction, and TestRecommendation records in PostgreSQL.
7. **FastAPI & React Dashboard**: Expose REST endpoints and display the pull request risk assessment, interactive React Flow dependency graph, and recommended test suite with rationale.
8. **GitHub Check Run Output**: Format and publish an informational GitHub Check Run report summary.

---

## 5. Phased Implementation Roadmap

### Phase 1: Project Foundations & Monorepo Architecture [STATUS: COMPLETED ✅]
- **Objective**: Establish the production-grade skeleton, database migrations, configuration, containerization, quality tooling, and CI pipeline.
- **Deliverables Completed**:
  - Monorepo directory structure established (`backend/`, `frontend/`, `scripts/`, `datasets/`, `docs/`, `examples/`, `.github/`).
  - Python 3.12+ configuration with `pyproject.toml`, FastAPI, SQLAlchemy 2.0 async/sync engine, Alembic migrations (`001_initial_schema.py`), Redis queue manager (`TaskQueueManager`), Pydantic v2 settings.
  - React 18 + TypeScript + Vite + Tailwind CSS frontend boilerplate with TanStack Query and Lucide icons.
  - Multi-stage Dockerfiles (`backend/Dockerfile`, `backend/worker.Dockerfile`, `frontend/Dockerfile`) and `docker-compose.yml` orchestrating PostgreSQL 16, Redis 7, Backend, Worker, Frontend.
  - Structured JSON logging (`JSONFormatter`), request correlation IDs (`CorrelationIdMiddleware`), and `/api/v1/health` readiness probe.
  - Quality toolchain configured and passing: Ruff (checks & format), MyPy (strict typing on 40 source files), Pytest (11 passing tests with 80% coverage), Vitest (2 passing tests), TypeScript typecheck.
  - GitHub Actions CI workflow (`.github/workflows/ci.yml`).
- **Acceptance Criteria Verification**:
  - `pytest` passes with 11/11 tests passing (0 failures).
  - `ruff check .` passes with 0 errors.
  - `ruff format --check .` confirms 51 files formatted.
  - `mypy app` passes with 0 errors across 40 source files.
  - Alembic offline SQL migration generated cleanly (`001_initial_schema`).
  - Frontend builds cleanly (`npm run build` with `tsc -b && vite build`) and passes Vitest tests (`npm test`).
  - Health check endpoint verified under healthy, degraded, and unhealthy mock conditions.

### Phase 2: GitHub Integration & Webhook Processing [STATUS: COMPLETED ✅]
- **Objective**: Build enterprise-grade GitHub App & Webhook ingestion engine with signature verification, deduplication, retry policies, and safe Git operations.
- **Deliverables Completed**:
  - `GitHubAuthService`: RS256 JWT generation with 2048-bit key support, installation access token retrieval, in-memory caching, and seamless fallback mode.
  - `GitHubClient`: Asynchronous GitHub REST client with automatic exponential backoff, jitter, rate limit retry (403/429), pagination over PR files, raw unified diff fetching, and unified error hierarchy (`GitHubAPIError`, `GitHubRateLimitError`, `GitHubAuthError`, `GitHubResourceNotFoundError`).
  - `WebhookHandlerService`: Ingress routing for `pull_request.opened`, `synchronize`, `reopened`, `closed`, and `installation` events; Redis `SETNX` delivery deduplication (24h TTL); automatic invalidation/superseding of outdated analyses when new commits arrive (`synchronize`); background task dispatching.
  - `RepositorySnapshotService`: Secure diff and content retrieval with strict path sanitization preventing directory traversal, absolute paths, and null-byte injection (`PathTraversalSecurityError`).
  - Pydantic v2 schemas: `GitHubWebhookPayload`, `GitHubFileChange`, `GitHubCommitSummary`, and `WebhookProcessingResult`.
- **Acceptance Criteria Verification**:
  - Invalid HMAC signatures return HTTP 401 with explicit error detail.
  - Duplicate deliveries return HTTP 200 with status `duplicate` and create 0 duplicate analyses or tasks.
  - Push of new commits (`pull_request.synchronize`) marks previous analyses `SUPERSEDED` and spawns a new analysis for the updated commit SHA.
  - Rate limiting, 404, and 401 API responses handled gracefully with verified backoff.
  - All 34 tests passing with zero errors across unit, integration, and security suites.

### Phase 3: Static Code Analysis & Dependency Engine
- **Objective**: Implement language-aware diff analysis, Tree-sitter AST parsing, Radon complexity extraction, and NetworkX dependency graph construction.
- **Deliverables**:
  - Tree-sitter Python parser mapping changed line diffs to exact function and class nodes.
  - Radon cyclomatic complexity and nesting depth extractor for files and functions.
  - NetworkX dependency analyzer extracting imports, callers, callees, fan-in, fan-out, and betweenness centrality.
  - Git history churn analyzer (file change frequency, author count, commit recency).
  - TypeScript parser extension via Tree-sitter TypeScript.
- **Acceptance Criteria**:
  - Controlled sample repository changes correctly identify modified functions, callers, and complexity deltas.
  - Unit tests verify graph metrics, boundary edge conditions, and syntax error resiliency.

### Phase 4: Historical Dataset Collection & Ground Truth Labeling
- **Objective**: Build reproducible scripts to collect pull requests, extract feature vectors, and assign transparent post-merge regression labels from open-source repositories.
- **Deliverables**:
  - `scripts/collect_dataset.py` with GitHub API rate-limit resilience.
  - Multi-tier regression labeling methodology (explicit reverts, linked bug-fix issues).
  - Data leakage prevention pipeline: chronological train/val/test split manifests and cross-repo holds.
  - Data validation and class imbalance reporting in `datasets/README.md`.
- **Acceptance Criteria**:
  - Deterministic dataset collection runs end-to-end.
  - Dataset manifest contains zero temporal leakage (verified by automated assertion).
  - Class distribution and label provenance documented.

### Phase 5: Regression Risk Prediction & ML Engine
- **Objective**: Develop baseline and supervised machine learning models (XGBoost, Random Forest, Logistic Regression) predicting post-merge regression risk with SHAP explainability.
- **Deliverables**:
  - Feature engineering pipeline (change size, complexity delta, churn, graph centrality).
  - Baseline models (Majority class, Change size heuristic).
  - Supervised training pipeline (`scripts/train_model.py`) with MLflow tracking and Joblib versioning.
  - SHAP tree explainer computing per-feature impact vectors.
  - Inference service integrated into FastAPI with model version provenance.
- **Acceptance Criteria**:
  - Models evaluated with PR-AUC, ROC-AUC, Brier score, and calibration plots.
  - FastAPI `/api/v1/analyses/{id}/risk` returns calibrated risk probability, model version, and top SHAP feature contributions.

### Phase 6: Intelligent Test Selection Engine
- **Objective**: Build a budgeted, risk-weighted test selection engine that maximizes regression detection while minimizing CI test execution duration.
- **Deliverables**:
  - Pytest discovery and coverage context parser (`test-context` coverage mapping).
  - Dependency-based test impact mapping (static call graph fallback when coverage is absent).
  - Budgeted greedy test selection optimizer maximizing marginal risk-weighted coverage.
  - Explainability module providing clear rationale and evidence level for each selected test.
  - Benchmark comparison suite (`scripts/benchmark_test_selection.py`) evaluating full suite vs random vs filename vs dependency vs CodeImpact selector.
- **Acceptance Criteria**:
  - Controlled test suite changes select optimal tests within time budget.
  - Test selection achieves >= 80% coverage retention with significant execution time reduction on benchmarks.
  - Every recommended test outputs human-readable explanation and evidence tier.

### Phase 7: FastAPI Backend Services & Endpoints
- **Objective**: Complete production REST API with authentication, pagination, idempotent job execution, metrics, and comprehensive OpenAPI specs.
- **Deliverables**:
  - Full REST API implementation for repositories, PRs, analyses, features, risk, dependencies, tests, metrics.
  - Prometheus-compatible metrics endpoint (`/api/v1/metrics`).
  - Background worker task execution and polling/webhook notifications.
  - Comprehensive unit and integration test coverage for all routes.
- **Acceptance Criteria**:
  - All endpoints pass integration tests with clean request/response schemas.
  - OpenAPI schema complies strictly with Pydantic v2 validation.

### Phase 8: React Dashboard & Visualization
- **Objective**: Build an interface displaying pull request risk, interactive React Flow dependency graphs, test intelligence, and ML evaluation analytics.
- **Deliverables**:
  - Overview Dashboard (repo overview, PR feed, risk distribution).
  - Pull Request Detail Page (risk gauge, SHAP factors, files changed, affected functions).
  - Interactive React Flow Dependency Graph (modified nodes, callers, tests, confirmed vs inferred edges).
  - Test Intelligence Page (recommended tests, duration savings, rationale, coverage stats).
  - ML Analytics Page (PR-AUC, ROC-AUC, feature importances, calibration plots, model versioning).
- **Acceptance Criteria**:
  - Responsive, accessible UI in light and dark mode.
  - Real backend data integration with zero mock fallback required when backend is running.
  - Fast rendering of complex graphs without layout jitter.

### Phase 9: GitHub Checks & PR Status Integration
- **Objective**: Publish rich analysis summaries, risk warnings, and recommended test suites as GitHub Check Runs.
- **Deliverables**:
  - GitHub Check Run publisher service (`services/github/checks.py`).
  - Markdown summary generator with collapsible feature breakdowns and test execution commands.
  - Stale check invalidation on new commit pushes (`synchronize` events).
- **Acceptance Criteria**:
  - Check Run summary renders cleanly with informational/neutral conclusion.
  - Avoids duplicate comment spamming on GitHub PR threads.

### Phase 10: Security Hardening & Reliability Engineering
- **Objective**: Enforce security boundaries, path traversal prevention, git argument sanitization, rate limiting, and structured observability.
- **Deliverables**:
  - Untrusted input sanitation and git safe-checkout isolation.
  - Worker timeout, retry, and dead-letter queue handling.
  - Structured JSON logging with request correlation IDs (`X-Correlation-ID`).
  - Security unit and integration tests.
- **Acceptance Criteria**:
  - Security test suite confirms injection and path traversal attempts are rejected.
  - Rate limiting and worker timeouts function as specified.

### Phase 11: End-to-End Testing & Failure Scenarios
- **Objective**: Validate the entire pipeline from webhook delivery to dashboard display and Check Run generation under normal and hostile failure conditions.
- **Deliverables**:
  - Comprehensive test suite (Unit, Integration, Security, E2E).
  - Mock GitHub fixtures and webhook delivery test harness.
  - Resiliency tests for invalid webhooks, missing coverage, malformed ASTs, network timeouts.
- **Acceptance Criteria**:
  - 100% of automated test suites pass consistently.
  - Edge cases and failure modes fail safely without unhandled 500 exceptions.

### Phase 12: Benchmarking & Research Evaluation
- **Objective**: Conduct rigorous empirical evaluations of regression risk prediction models and test selection optimization.
- **Deliverables**:
  - Benchmark scripts (`scripts/evaluate_model.py`, `scripts/benchmark_test_selection.py`).
  - Comparative tables: baseline models vs XGBoost (PR-AUC, ROC-AUC, Brier score).
  - Test selection ablation studies: random vs filename vs dependency vs CodeImpact.
  - System performance profiling (latency vs PR lines/files changed).
- **Acceptance Criteria**:
  - Benchmark outputs are saved into versioned JSON/CSV artifacts.
  - Empirical results documented with confidence metrics and no fabricated numbers.

### Phase 13: Containerization & Docker Compose Deployment
- **Objective**: Create multi-stage, secure, reproducible Docker environments for local development and self-hosted deployment.
- **Deliverables**:
  - Multi-stage Dockerfiles for backend, worker, and frontend.
  - Production-ready `docker-compose.yml` with health checks, database volumes, non-root users.
  - One-command startup script and seeding utility (`scripts/bootstrap_demo.py`).
- **Acceptance Criteria**:
  - `docker compose up --build` boots all services with passing health checks.
  - Demo script seeds sample repository, pull requests, analyses, and test metadata cleanly.

### Phase 14: Comprehensive Documentation & Portfolio Presentation
- **Objective**: Author world-class documentation, architecture diagrams, user guides, and research methodology write-ups.
- **Deliverables**:
  - Master `README.md` with system overview, architecture diagrams, and quickstart.
  - Detailed documentation in `docs/`: `architecture.md`, `data_collection.md`, `feature_engineering.md`, `model_evaluation.md`, `test_selection.md`, `security.md`, `deployment.md`.
  - Mermaid diagrams for ingestion, AST analysis, test selection, and ML pipelines.
  - Sample repository (`examples/sample_python_repo/`) demonstrating full analysis flow.
- **Acceptance Criteria**:
  - All documentation is complete, technically precise, and directly verifiable against the codebase.

---

## 6. Execution Protocol & Verification Gates

For each phase:
1. **Design & Implementation**: Implement the specific modules according to production standards.
2. **Automated Testing**: Write and run unit, integration, and property tests.
3. **Quality Tooling**: Run `ruff check`, `ruff format`, `mypy`, and frontend checks.
4. **Verification & Audit**: Verify acceptance criteria explicitly.
5. **Update plan.md**: Mark status, document learnings, and record metric milestones before advancing.

Let's proceed immediately to Phase 1.
