#!/usr/bin/env python3
"""
scripts/bootstrap_demo.py
Seeds CodeImpact database with realistic repositories, pull requests, AST diffs,
risk predictions across LOW, MEDIUM, HIGH, and CRITICAL risk tiers, and intelligent test selection plans.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# Configure matplotlib temporary directory for sandbox compatibility
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from app.core.config import settings
from app.core.database import Base
from app.core.logging import get_logger
from app.models.analysis import Analysis
from app.models.model_version import ModelVersion
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.services.analysis.orchestration_service import analysis_orchestration_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = get_logger("scripts.bootstrap_demo")

# Realistic Diffs and Source Code Fixtures
SAMPLE_REPOS = [
    {
        "github_id": 14091895,
        "owner": "tiangolo",
        "name": "fastapi",
        "full_name": "tiangolo/fastapi",
        "default_branch": "master",
    },
    {
        "github_id": 1362490,
        "owner": "psf",
        "name": "requests",
        "full_name": "psf/requests",
        "default_branch": "main",
    },
    {
        "github_id": 596892,
        "owner": "pallets",
        "name": "flask",
        "full_name": "pallets/flask",
        "default_branch": "main",
    },
]

DEMO_SCENARIOS = [
    {
        "repo_full_name": "tiangolo/fastapi",
        "pr_number": 101,
        "title": "docs(openapi): clarify response model type annotations in tutorial",
        "author": "docs-contributor",
        "base_sha": "a101000000000000000000000000000000000000",
        "head_sha": "a101111111111111111111111111111111111111",
        "base_ref": "master",
        "head_ref": "docs/response-model-typing",
        "diff_text": """diff --git a/docs_src/tutorial/item_models.py b/docs_src/tutorial/item_models.py
index 1000001..2000001 100644
--- a/docs_src/tutorial/item_models.py
+++ b/docs_src/tutorial/item_models.py
@@ -1,4 +1,5 @@
-from typing import Optional
+from typing import Optional, Union
 
 class ItemModel:
-    name: str
+    # Updated docstring annotation
+    name: Union[str, None]
""",
        "base_files": {
            "docs_src/tutorial/item_models.py": "from typing import Optional\n\nclass ItemModel:\n    name: str\n"
        },
        "head_files": {
            "docs_src/tutorial/item_models.py": "from typing import Optional, Union\n\nclass ItemModel:\n    # Updated docstring annotation\n    name: Union[str, None]\n",
            "tests/test_tutorial_models.py": "from docs_src.tutorial.item_models import ItemModel\n\ndef test_item_model_instantiation():\n    m = ItemModel()\n    assert m is not None\n",
            "tests/test_tutorial_validation.py": "def test_validation(): pass\n",
            "tests/test_tutorial_docs.py": "def test_docs(): pass\n",
            "tests/test_tutorial_extra.py": "def test_extra(): pass\n",
        },
        "feature_overrides": {
            "test_coverage_ratio": 0.95,
            "recent_change_concentration": 0.1,
            "mean_change_frequency": 0.1,
        },
        "coverage": {
            "files": {"docs_src/tutorial/item_models.py": {"executed_lines": [1, 3, 5]}}
        },
    },
    {
        "repo_full_name": "psf/requests",
        "pr_number": 102,
        "title": "feat(pool): implement connection pool timeout and exponential backoff retry",
        "author": "network-ninja",
        "base_sha": "b202000000000000000000000000000000000000",
        "head_sha": "b202222222222222222222222222222222222222",
        "base_ref": "main",
        "head_ref": "feat/pool-retry-backoff",
        "diff_text": """diff --git a/requests/adapters.py b/requests/adapters.py
index 1000002..2000002 100644
--- a/requests/adapters.py
+++ b/requests/adapters.py
@@ -20,6 +20,15 @@ def send_request(request, timeout=30):
     conn = pool.get_connection()
-    return conn.send(request)
+    for attempt in range(3):
+        try:
+            if conn.is_healthy():
+                return conn.send(request, timeout=timeout)
+            conn = pool.reconnect()
+        except ConnectionError:
+            if attempt == 2:
+                raise
+    return None
""",
        "base_files": {
            "requests/adapters.py": "def send_request(request, timeout=30):\n    conn = pool.get_connection()\n    return conn.send(request)\n"
        },
        "head_files": {
            "requests/adapters.py": (
                "def send_request(request, timeout=30):\n"
                "    conn = pool.get_connection()\n"
                "    for attempt in range(3):\n"
                "        try:\n"
                "            if conn.is_healthy():\n"
                "                return conn.send(request, timeout=timeout)\n"
                "            conn = pool.reconnect()\n"
                "        except ConnectionError:\n"
                "            if attempt == 2:\n"
                "                raise\n"
                "    return None\n"
            ),
            "tests/test_adapters.py": (
                "from requests.adapters import send_request\n"
                "def test_send_request_success(): pass\n"
                "def test_send_request_retry_on_failure(): pass\n"
            ),
            "tests/test_sessions.py": "def test_sessions(): pass\n",
            "tests/test_cookies.py": "def test_cookies(): pass\n",
            "tests/test_auth.py": "def test_auth(): pass\n",
            "tests/test_hooks.py": "def test_hooks(): pass\n",
        },
        "feature_overrides": {
            "change_size": 180.0,
            "lines_added": 140.0,
            "delta_average_complexity": 6.0,
            "affected_callers_count": 18.0,
            "recent_change_concentration": 0.55,
            "mean_change_frequency": 0.45,
            "test_coverage_ratio": 0.65,
        },
        "coverage": {
            "files": {"requests/adapters.py": {"executed_lines": [20, 21, 22, 23, 24]}}
        },
    },
    {
        "repo_full_name": "tiangolo/fastapi",
        "pr_number": 103,
        "title": "refactor(security): overhaul session token verification & JWT claim cache",
        "author": "sec-lead",
        "base_sha": "c303000000000000000000000000000000000000",
        "head_sha": "c303333333333333333333333333333333333333",
        "base_ref": "master",
        "head_ref": "refactor/session-jwt-auth",
        "diff_text": """diff --git a/fastapi/security/jwt_auth.py b/fastapi/security/jwt_auth.py
index 1000003..2000003 100644
--- a/fastapi/security/jwt_auth.py
+++ b/fastapi/security/jwt_auth.py
@@ -35,8 +35,26 @@ class JWTAuthenticator:
     def verify_token(self, token_str: str, scopes: list[str]) -> dict:
-        payload = jwt.decode(token_str, self.secret_key)
-        return payload
+        if not token_str or len(token_str) > 4096:
+            raise SecurityTokenError("Malformed or oversized token")
+        for disallowed in self.revocation_list:
+            if token_str.startswith(disallowed):
+                raise TokenRevokedError("Token has been invalidated")
+        try:
+            payload = jwt.decode(token_str, self.secret_key, algorithms=["RS256"])
+            for required_scope in scopes:
+                if required_scope not in payload.get("scopes", []):
+                    raise InsufficientScopeError(f"Missing {required_scope}")
+            if payload.get("exp", 0) < time.time():
+                raise TokenExpiredError("Token expired")
+            return payload
+        except Exception as e:
+            self.audit_logger.record_failure(token_str[:8], str(e))
+            raise
""",
        "base_files": {
            "fastapi/security/jwt_auth.py": (
                "class JWTAuthenticator:\n"
                "    def verify_token(self, token_str: str, scopes: list[str]) -> dict:\n"
                "        payload = jwt.decode(token_str, self.secret_key)\n"
                "        return payload\n"
            )
        },
        "head_files": {
            "fastapi/security/jwt_auth.py": (
                "class JWTAuthenticator:\n"
                "    def verify_token(self, token_str: str, scopes: list[str]) -> dict:\n"
                "        if not token_str or len(token_str) > 4096:\n"
                "            raise SecurityTokenError('Malformed or oversized token')\n"
                "        for disallowed in self.revocation_list:\n"
                "            if token_str.startswith(disallowed):\n"
                "                raise TokenRevokedError('Token has been invalidated')\n"
                "        try:\n"
                "            payload = jwt.decode(token_str, self.secret_key, algorithms=['RS256'])\n"
                "            for required_scope in scopes:\n"
                "                if required_scope not in payload.get('scopes', []):\n"
                "                    raise InsufficientScopeError(f'Missing {required_scope}')\n"
                "            if payload.get('exp', 0) < time.time():\n"
                "                raise TokenExpiredError('Token expired')\n"
                "            return payload\n"
                "        except Exception as e:\n"
                "            self.audit_logger.record_failure(token_str[:8], str(e))\n"
                "            raise\n"
            ),
            "tests/test_jwt_auth.py": (
                "from fastapi.security.jwt_auth import JWTAuthenticator\n"
                "def test_jwt_valid_signature(): pass\n"
                "def test_jwt_expired_token(): pass\n"
                "def test_jwt_insufficient_scopes(): pass\n"
                "def test_jwt_revoked_blacklist(): pass\n"
            ),
            "tests/test_openapi_security.py": "def test_openapi(): pass\n",
            "tests/test_oauth2.py": "def test_oauth2(): pass\n",
            "tests/test_cors.py": "def test_cors(): pass\n",
            "tests/test_rate_limits.py": "def test_rate_limits(): pass\n",
        },
        "feature_overrides": {
            "change_size": 650.0,
            "lines_added": 520.0,
            "delta_average_complexity": 14.0,
            "affected_callers_count": 48.0,
            "mean_betweenness_centrality": 0.45,
            "recent_change_concentration": 0.85,
            "test_coverage_ratio": 0.20,
            "historical_test_failure_frequency": 0.40,
        },
        "coverage": {
            "files": {
                "fastapi/security/jwt_auth.py": {"executed_lines": list(range(35, 55))}
            }
        },
    },
    {
        "repo_full_name": "pallets/flask",
        "pr_number": 104,
        "title": "refactor(engine): rewrite distributed transaction state manager & locking protocol",
        "author": "core-architect",
        "base_sha": "d404000000000000000000000000000000000000",
        "head_sha": "d404444444444444444444444444444444444444",
        "base_ref": "main",
        "head_ref": "refactor/distributed-tx-protocol",
        "diff_text": """diff --git a/flask/transactions/manager.py b/flask/transactions/manager.py
index 1000004..2000004 100644
--- a/flask/transactions/manager.py
+++ b/flask/transactions/manager.py
@@ -10,12 +10,48 @@ class TransactionManager:
     def commit_distributed(self, tx_id: str, nodes: list[str]) -> bool:
-        for node in nodes:
-            node.commit(tx_id)
-        return True
+        acquired_locks = []
+        try:
+            for node in nodes:
+                lock = node.acquire_lock(tx_id, timeout=10.0)
+                if not lock:
+                    for l in acquired_locks:
+                        l.release()
+                    return False
+                acquired_locks.append(lock)
+            for node in nodes:
+                if not node.prepare(tx_id):
+                    for l in acquired_locks:
+                        l.release()
+                    raise ConsensusFailureError("Two-phase commit prepare rejected")
+            for node in nodes:
+                while not node.is_ready():
+                    time.sleep(0.01)
+                node.commit(tx_id)
+            return True
+        except Exception as tx_err:
+            self.logger.critical(f"Distributed transaction {tx_id} aborted: {tx_err}")
+            for node in nodes:
+                try:
+                    node.abort(tx_id)
+                except Exception:
+                    pass
+            raise
""",
        "base_files": {
            "flask/transactions/manager.py": (
                "class TransactionManager:\n"
                "    def commit_distributed(self, tx_id: str, nodes: list[str]) -> bool:\n"
                "        for node in nodes:\n"
                "            node.commit(tx_id)\n"
                "        return True\n"
            )
        },
        "head_files": {
            "flask/transactions/manager.py": (
                "class TransactionManager:\n"
                "    def commit_distributed(self, tx_id: str, nodes: list[str]) -> bool:\n"
                "        acquired_locks = []\n"
                "        try:\n"
                "            for node in nodes:\n"
                "                lock = node.acquire_lock(tx_id, timeout=10.0)\n"
                "                if not lock:\n"
                "                    for l in acquired_locks:\n"
                "                        l.release()\n"
                "                    return False\n"
                "                acquired_locks.append(lock)\n"
                "            for node in nodes:\n"
                "                if not node.prepare(tx_id):\n"
                "                    for l in acquired_locks:\n"
                "                        l.release()\n"
                "                    raise ConsensusFailureError('Two-phase commit prepare rejected')\n"
                "            for node in nodes:\n"
                "                while not node.is_ready():\n"
                "                    time.sleep(0.01)\n"
                "                node.commit(tx_id)\n"
                "            return True\n"
                "        except Exception as tx_err:\n"
                "            self.logger.critical(f'Distributed transaction {tx_id} aborted: {tx_err}')\n"
                "            for node in nodes:\n"
                "                try:\n"
                "                    node.abort(tx_id)\n"
                "                except Exception:\n"
                "                    pass\n"
                "            raise\n"
            ),
            "tests/test_tx_manager.py": (
                "from flask.transactions.manager import TransactionManager\n"
                "def test_tx_commit_happy_path(): pass\n"
                "def test_tx_lock_timeout_rejection(): pass\n"
                "def test_tx_consensus_abort(): pass\n"
                "def test_tx_node_recovery(): pass\n"
            ),
            "tests/test_views.py": "def test_views(): pass\n",
            "tests/test_blueprints.py": "def test_blueprints(): pass\n",
            "tests/test_signals.py": "def test_signals(): pass\n",
            "tests/test_templating.py": "def test_templating(): pass\n",
        },
        "feature_overrides": {
            "change_size": 2500.0,
            "lines_added": 1900.0,
            "delta_average_complexity": 30.0,
            "delta_max_complexity": 55.0,
            "affected_callers_count": 220.0,
            "downstream_dependencies_count": 95.0,
            "mean_betweenness_centrality": 0.85,
            "recent_change_concentration": 0.98,
            "test_coverage_ratio": 0.05,
            "historical_test_failure_frequency": 0.85,
            "public_api_changes_count": 12.0,
        },
        "coverage": {
            "files": {
                "flask/transactions/manager.py": {"executed_lines": list(range(10, 50))}
            }
        },
    },
]


async def bootstrap_demo() -> None:
    target_db_url = os.environ.get("DATABASE_URL", settings.DATABASE_URL)
    logger.info(f"Connecting to database at {target_db_url}...")

    # Attempt connecting to configured database, fallback to local sqlite if postgres is unavailable
    try:
        engine = create_async_engine(target_db_url, echo=False)
        async with engine.connect() as conn:
            pass
    except Exception as conn_err:  # noqa: BLE001
        logger.warning(
            f"Configured database {target_db_url} is unavailable ({conn_err}). "
            "Falling back to local SQLite database at codeimpact_demo.db for zero-config demonstration."
        )
        target_db_url = "sqlite+aiosqlite:///codeimpact_demo.db"
        engine = create_async_engine(target_db_url, echo=False)

    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        # 1. Seed or update ModelVersion
        logger.info("Registering production Risk Model Version...")
        mv_stmt = select(ModelVersion).where(ModelVersion.version == "1.0.0")
        mv = (await session.execute(mv_stmt)).scalar_one_or_none()
        if not mv:
            mv = ModelVersion(
                name="CodeImpact XGBoost Risk Predictor",
                version="1.0.0",
                algorithm="xgboost",
                pr_auc=0.2256,
                roc_auc=0.5765,
                brier_score=0.1775,
                is_active=True,
                artifact_path="backend/app/ml/models_store/risk_model_v1.joblib",
            )
            session.add(mv)
            await session.flush()

        # 2. Seed Repositories
        repo_map: dict[str, Repository] = {}
        for r_spec in SAMPLE_REPOS:
            r_stmt = select(Repository).where(
                Repository.full_name == r_spec["full_name"]
            )
            repo = (await session.execute(r_stmt)).scalar_one_or_none()
            if not repo:
                repo = Repository(
                    github_id=r_spec["github_id"],
                    owner=r_spec["owner"],
                    name=r_spec["name"],
                    full_name=r_spec["full_name"],
                    default_branch=r_spec["default_branch"],
                    is_active=True,
                )
                session.add(repo)
                await session.flush()
            repo_map[r_spec["full_name"]] = repo

        # 3. Seed Pull Requests and Execute Pipelines
        logger.info(
            "Executing static analysis, risk inference, and test selection for demo PRs..."
        )
        created_analyses = []
        for scenario in DEMO_SCENARIOS:
            repo = repo_map[scenario["repo_full_name"]]
            pr_stmt = select(PullRequest).where(
                PullRequest.repository_id == repo.id,
                PullRequest.pr_number == scenario["pr_number"],
            )
            pr = (await session.execute(pr_stmt)).scalar_one_or_none()
            if not pr:
                pr = PullRequest(
                    repository_id=repo.id,
                    github_pr_id=repo.github_id * 1000 + scenario["pr_number"],
                    pr_number=scenario["pr_number"],
                    title=scenario["title"],
                    state="open",
                    author=scenario["author"],
                    base_sha=scenario["base_sha"],
                    head_sha=scenario["head_sha"],
                    base_ref=scenario["base_ref"],
                    head_ref=scenario["head_ref"],
                )
                session.add(pr)
                await session.flush()

            # Create Analysis
            analysis = Analysis(
                pull_request_id=pr.id,
                commit_sha=pr.head_sha,
                base_sha=pr.base_sha,
                status="PENDING",
                analysis_version="1.0.0",
            )
            session.add(analysis)
            await session.flush()

            # Execute full pipeline
            res = await analysis_orchestration_service.execute_analysis_pipeline(
                analysis_id=analysis.id,
                diff_text=scenario["diff_text"],
                base_files=scenario["base_files"],
                head_files=scenario["head_files"],
                coverage_data=scenario["coverage"],
                feature_overrides=scenario.get("feature_overrides"),
                db=session,
            )

            created_analyses.append((pr, analysis, res))

        await session.commit()

    await engine.dispose()

    # Print summary
    print("\n" + "=" * 70)
    print(" 🚀 CODEIMPACT DEMO ENVIRONMENT READY!")
    print("=" * 70)
    print(
        f"Loaded {len(SAMPLE_REPOS)} Repositories and {len(created_analyses)} Realistic Pull Requests:"
    )
    for pr, analysis, res in created_analyses:
        pred = res["prediction"]
        tier = pred["risk_tier"]
        score = int(pred["risk_score"] * 100)
        tests = res["test_selection"]["selected_tests_count"]
        savings = res["test_selection"]["time_savings_percent"]
        print(f"\n  • PR #{pr.pr_number}: {pr.title[:50]}...")
        print(
            f"    Risk: {tier} ({score}%) | Confidence: [{pred['confidence_lower']:.2f}, {pred['confidence_upper']:.2f}]"
        )
        print(
            f"    Selected Tests: {tests} recommended ({savings:.1f}% suite time saved)"
        )
        print(f"    Analysis ID: {analysis.id}")
        print(f"    Dashboard Link: http://localhost:5173/pull-requests/{pr.id}")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(bootstrap_demo())
