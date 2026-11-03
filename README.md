# CodeImpact — Predictive Software Change Risk Analyzer

[![CI](https://github.com/codeimpact/codeimpact/actions/workflows/ci.yml/badge.svg)](https://github.com/codeimpact/codeimpact/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://react.dev)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**CodeImpact** is a developer-infrastructure platform that analyzes GitHub pull requests before merge, reconstructing AST syntax hierarchies, measuring cyclomatic complexity deltas, predicting post-merge regression risk via supervised machine learning, and recommending a budgeted, risk-weighted subset of tests to optimize CI turnaround.

---

## 1. System Architecture

```mermaid
flowchart TD
    subgraph GitHub ["GitHub Infrastructure"]
        PR[Pull Request Opened / Synchronize]
        Checks[GitHub Check Run Publisher]
    end

    subgraph Ingestion ["Ingestion & Verification"]
        Receiver["/api/v1/webhooks/github"]
        HMAC[HMAC-SHA256 Signature Verification]
        Dedupe[Redis Event Deduplication]
    end

    subgraph Queue ["Background Task Queue"]
        RQ[Redis Queue Worker]
    end

    subgraph StaticEngine ["Static Code Analysis Engine"]
        TS[Tree-sitter Python & TS AST Parser]
        Radon[Radon Cyclomatic Complexity]
        DepGraph[NetworkX Dependency Graph]
        GitChurn[Git Churn & Contributor Analyzer]
    end

    subgraph ML ["Predictive Risk Modeling"]
        FeatAgg[Feature Aggregation Layer]
        Model[Calibrated XGBoost Classifier]
        SHAP[TreeSHAP Feature Attributions]
    end

    subgraph TestSelection ["Intelligent Test Selection"]
        TestMap[Coverage Context & Impact Mapper]
        Optimizer[Budgeted Marginal Coverage Optimizer]
    end

    subgraph Presentation ["Presentation & API"]
        PG[(PostgreSQL 16 Persistence)]
        API[FastAPI REST API]
        UI[React 18 Dashboard]
    end

    PR --> Receiver
    Receiver --> HMAC
    HMAC --> Dedupe
    Dedupe --> RQ
    RQ --> TS
    TS --> Radon
    TS --> DepGraph
    TS --> GitChurn
    
    Radon --> FeatAgg
    DepGraph --> FeatAgg
    GitChurn --> FeatAgg
    
    FeatAgg --> Model
    Model --> SHAP
    
    TS --> TestMap
    DepGraph --> TestMap
    Model --> Optimizer
    TestMap --> Optimizer
    
    SHAP --> PG
    Optimizer --> PG
    
    PG --> API
    API --> UI
    API --> Checks
```

---

## 2. Key Capabilities

- **AST-Level Change Localization**: Tree-sitter maps changed line hunks to function and class nodes.
- **Cyclomatic Complexity Delta**: Radon calculates $\Delta CC$ per modified scope.
- **Dependency Reification**: NetworkX models caller/callee graphs, fan-in, fan-out, and betweenness centrality.
- **Supervised Regression Risk**: Calibrated XGBoost predicting regression probabilities with TreeSHAP explanations.
- **Budgeted Test Selection**: Greedy marginal risk-weighted coverage optimizer recommending tests under developer time budgets.
- **GitHub Check Runs**: Automated status summaries published directly onto pull request review workflows.

---

## 3. Technology Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.0 (asyncpg / psycopg2), Alembic, Pydantic v2, Redis, RQ
- **Static Analysis**: Tree-sitter, tree-sitter-python, tree-sitter-typescript, Radon, NetworkX, GitPython
- **Machine Learning**: Scikit-learn, XGBoost, SHAP, MLflow, Pandas, NumPy, Joblib
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, React Flow, Recharts, Lucide Icons
- **Infrastructure**: Docker, Docker Compose, GitHub Actions, PostgreSQL 16, Redis 7

---

## 4. Repository Structure

```
├── backend/
│   ├── app/
│   │   ├── api/routes/       # REST and Webhook endpoints
│   │   ├── core/             # Config, security, logging, database
│   │   ├── models/           # SQLAlchemy ORM declarative models
│   │   ├── schemas/          # Pydantic v2 validation models
│   │   ├── services/         # Domain services (GitHub, AST, ML, tests)
│   │   ├── workers/          # Background worker queue abstraction
│   │   └── ml/               # Datasets, training, inference, evaluation
│   ├── alembic/              # Database schema versioning migrations
│   ├── tests/                # Unit, integration, security test suites
│   └── pyproject.toml        # Ruff, MyPy, and Pytest configuration
├── frontend/
│   ├── src/
│   │   ├── components/       # Reusable UI widgets
│   │   ├── pages/            # Overview, PR Detail, Impact Graph, Test Intel
│   │   └── App.tsx           # Application shell & route setup
│   └── package.json          # Vite + React + Tailwind dependencies
├── datasets/                 # Historical PR dataset specifications & manifests
├── docs/                     # Comprehensive architecture and engineering specifications
├── scripts/                  # Bootstrapping, training, evaluation, benchmark utilities
├── docker-compose.yml        # Orchestration for PostgreSQL, Redis, Backend, Worker, UI
└── plan.md                   # Phased execution roadmap and verification gates
```

---

## 5. Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- Node.js 20+
- Docker & Docker Compose (optional, for containerized run)

### Running with Docker Compose
```bash
# Clone the repository
git clone https://github.com/codeimpact/codeimpact.git
cd codeimpact

# Launch PostgreSQL, Redis, Backend, Worker, and Frontend
docker compose up --build
```
Access points:
- **Web Dashboard**: [http://localhost:5173](http://localhost:5173) or [http://localhost:80](http://localhost:80)
- **FastAPI Interactive Docs**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **Health Check Probe**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **Prometheus Metrics**: [http://localhost:8000/api/v1/metrics](http://localhost:8000/api/v1/metrics)

### Running Locally without Docker

1. **Start Backend**:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt

# Run migrations (or use SQLite test database)
cd backend
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --port 8000
```

2. **Start Frontend**:
```bash
cd frontend
npm install
npm run dev
```

---

## 6. Testing & Quality Verification

### Run Backend Tests & Coverage
```bash
cd backend
pytest --cov=app --cov-report=term-missing tests/
```

### Run Ruff Linter & Formatting
```bash
cd backend
ruff check .
ruff format --check .
```

### Run MyPy Static Type Checking
```bash
cd backend
mypy app
```

### Run Frontend Tests & Build
```bash
cd frontend
npm test
npm run build
```

---

## 7. Current Project Status

- [x] **Phase 1 — Project Foundations**: Monorepo layout, FastAPI backend, SQLAlchemy 2.0 models, Alembic migrations, Redis queue manager, React + TypeScript frontend, Docker Compose, structured JSON logging, CI workflow, and passing test suites.
- [ ] **Phase 2 — GitHub Integration**: GitHub App, Webhook HMAC-SHA256 signature verification, delivery deduplication, PyGithub client.
- [ ] **Phase 3 — Static Code Analysis Engine**: Tree-sitter AST parsing, Radon complexity deltas, NetworkX dependency graphs.
- [ ] **Phase 4 — Historical Dataset Collection**: Multi-tier regression labeling methodology and chronological split manifests.
- [ ] **Phase 5 — Regression Risk Prediction**: Calibrated XGBoost model training and SHAP local attributions.
- [ ] **Phase 6 — Intelligent Test Selection**: Budgeted greedy marginal coverage optimizer and benchmark evaluations.
- [ ] **Phase 7 — Complete REST APIs**: Idempotent analysis execution, pagination, and OpenAPI specification.
- [ ] **Phase 8 — React Dashboard**: React Flow dependency visualization, risk gauges, and test recommendations.
- [ ] **Phase 9 — GitHub Checks Integration**: Informational Check Run summary publisher.
- [ ] **Phase 10 — Security Hardening & Observability**: Git sanitization, rate limiting, and structured telemetry.
- [ ] **Phase 11 — Comprehensive Testing**: End-to-end webhook-to-dashboard tests and failure injection suites.
- [ ] **Phase 12 — Benchmarks & Empirical Evaluation**: Predictive model and test selection ablation benchmarks.
- [ ] **Phase 13 — Production Deployment**: Multi-stage hardened containers and demo bootstrapping.
- [ ] **Phase 14 — Complete Documentation**: In-depth technical guides and case studies.
