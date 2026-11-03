# Deployment, Containerization & Operations Guide

## 1. Architecture Topology
CodeImpact is packaged as a containerized modular monolith with asynchronous background job workers, Redis queue buffering, and PostgreSQL persistence.

```
       [ Client Browser / GitHub Webhooks ]
                        |
                        v
                 [ Nginx Reverse Proxy / Frontend (Port 80 / 5173) ]
                        |
                        v
                 [ FastAPI API Server (Port 8000) ]
                   /                  \
                  v                    v
         [ Redis 7 (Port 6379) ]    [ PostgreSQL 16 (Port 5432) ]
                  |                    ^
                  v                    |
       [ Background Worker (RQ) ] -----+
```

---

## 2. Quickstart with Docker Compose

### Prerequisites
- Docker Engine $\ge 24.0$
- Docker Compose $\ge 2.20$

### Launch All Services
```bash
# 1. Clone repository and navigate to root
cd "CodeImpact — Predictive Software Change Risk Analyzer"

# 2. Copy and customize environment variables
cp .env.example .env

# 3. Build and launch containers in background
docker compose up -d --build

# 4. Verify running health status
docker compose ps
```

Services will be accessible at:
- **Web Dashboard**: `http://localhost:5173` or `http://localhost:80`
- **FastAPI REST API Docs**: `http://localhost:8000/docs`
- **Health Probes**: `http://localhost:8000/api/v1/health`
- **Prometheus Metrics**: `http://localhost:8000/api/v1/metrics/prometheus`

---

## 3. Environment Variable Configuration

| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Deployment mode: `development`, `testing`, `production` |
| `DATABASE_URL` | `postgresql+asyncpg://codeimpact:codeimpact_dev_password@postgres:5432/codeimpact_db` | Async SQLAlchemy PostgreSQL connection string |
| `SYNC_DATABASE_URL` | `postgresql+psycopg2://codeimpact:codeimpact_dev_password@postgres:5432/codeimpact_db` | Sync SQLAlchemy connection string for Alembic & RQ |
| `REDIS_URL` | `redis://redis:6379/0` | Redis instance for job queue & delivery deduplication |
| `GITHUB_WEBHOOK_SECRET` | `development_webhook_secret_key` | Secret key used to verify HMAC-SHA256 signatures |
| `GITHUB_APP_ID` | `""` | GitHub App ID for check run publication |
| `GITHUB_APP_PRIVATE_KEY`| `""` | PEM-encoded RSA private key for GitHub App authentication |
| `ML_MODEL_ARTIFACTS_PATH`| `./backend/app/ml/models_store` | Path to serialized `.joblib` model weights |

---

## 4. Database Migrations with Alembic

Alembic manages all schema revisions. Migrations are executed automatically or manually:

```bash
# Apply pending database migrations
docker compose exec backend alembic upgrade head

# Generate a new migration revision
docker compose exec backend alembic revision --autogenerate -m "Add new indexes"
```

---

## 5. Background Task Processing

Background analyses are processed asynchronously using Redis Queue (`RQ`). To scale workers horizontally:
```bash
# Scale worker pool to 4 instances
docker compose up -d --scale worker=4
```

---

## 6. Monitoring, Health Checks & Observability

### Health & Readiness Probes
- `GET /api/v1/health`: Liveness probe verifying process responsiveness.
- `GET /api/v1/health/ready`: Readiness probe verifying active database queries and Redis ping.

### Prometheus Metrics
- `GET /api/v1/metrics/prometheus`: Prometheus-compatible exposition format tracking:
  - `codeimpact_http_requests_total`: Request volume by path, method, and HTTP status.
  - `codeimpact_http_request_duration_seconds`: Request latency histogram.
  - `codeimpact_analyses_total`: Completed, failed, and superseded analysis counts.
  - `codeimpact_risk_prediction_score`: Risk score distribution gauge.

---

## 7. Production Readiness Checklist

- [x] All 92 backend tests passing with zero failures.
- [x] All frontend unit tests and production Vite builds passing (`npm run build`).
- [x] Timing-safe HMAC signature verification enabled.
- [x] Path traversal fuzzing and untrusted input sanitization verified.
- [x] Database migrations versioned in Alembic.
- [x] Health and readiness endpoints configured for container orchestrators.
- [x] Multi-stage slim Docker images running under non-root user (`codeimpact`).
