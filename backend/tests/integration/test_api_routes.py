import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis, AnalysisStatus
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.services.analysis.orchestration_service import analysis_orchestration_service


@pytest.fixture
async def seeded_repo_and_pr(db_session: AsyncSession):
    repo = Repository(
        id=str(uuid.uuid4()),
        github_id=1234567,
        full_name="org/test-repo",
        owner="org",
        name="test-repo",
        default_branch="main",
        is_active=True,
    )
    db_session.add(repo)
    await db_session.flush()

    pr = PullRequest(
        id=str(uuid.uuid4()),
        repository_id=repo.id,
        github_pr_id=987654,
        pr_number=42,
        title="Add user authentication and rate limiting",
        author="octocat",
        base_ref="main",
        head_ref="feature/auth",
        base_sha="base_sha_1234",
        head_sha="head_sha_5678",
        state="open",
    )
    db_session.add(pr)
    await db_session.commit()
    await db_session.refresh(repo)
    await db_session.refresh(pr)
    return repo, pr


async def test_repository_api_endpoints(client: AsyncClient):
    # 1. Register repo
    create_resp = await client.post(
        "/api/v1/repositories",
        json={"full_name": "google/sample-project", "default_branch": "main"},
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["full_name"] == "google/sample-project"
    repo_id = created_data["id"]

    # 2. List repos
    list_resp = await client.get("/api/v1/repositories")
    assert list_resp.status_code == 200
    repos = list_resp.json()
    assert any(r["id"] == repo_id for r in repos)

    # 3. Get single repo
    get_resp = await client.get(f"/api/v1/repositories/{repo_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == repo_id


async def test_pull_requests_api_endpoints(client: AsyncClient, seeded_repo_and_pr):
    repo, pr = seeded_repo_and_pr

    # 1. List PRs
    resp = await client.get(f"/api/v1/pull-requests?repository_id={repo.id}")
    assert resp.status_code == 200
    prs = resp.json()
    assert len(prs) == 1
    assert prs[0]["pr_number"] == 42

    # 2. Trigger analysis
    trig_resp = await client.post(f"/api/v1/pull-requests/{pr.id}/analyze")
    assert trig_resp.status_code == 200
    assert "analysis_id" in trig_resp.json()


async def test_end_to_end_analysis_orchestration_and_api(
    client: AsyncClient,
    db_session: AsyncSession,
    seeded_repo_and_pr,
):
    repo, pr = seeded_repo_and_pr

    # Create initial queued analysis record
    analysis = Analysis(
        id=str(uuid.uuid4()),
        pull_request_id=pr.id,
        commit_sha=pr.head_sha,
        base_sha=pr.base_sha,
        status=AnalysisStatus.QUEUED.value,
        analysis_version="1.0.0",
    )
    db_session.add(analysis)
    await db_session.commit()

    diff_text = """diff --git a/app/auth.py b/app/auth.py
index 1111111..2222222 100644
--- a/app/auth.py
+++ b/app/auth.py
@@ -10,3 +10,6 @@ def verify_credentials(user, password):
+    if not user or not password:
+        return False
+    return True
"""
    base_files = {
        "app/auth.py": "def verify_credentials(user, password):\n    pass\n",
    }
    head_files = {
        "app/auth.py": "def verify_credentials(user, password):\n    if not user or not password:\n        return False\n    return True\n",
        "tests/test_auth.py": "from app.auth import verify_credentials\ndef test_verify():\n    assert verify_credentials('u', 'p')\n",
    }
    coverage_data = {
        "files": {
            "app/auth.py": {
                "executed_lines": [10, 11, 12],
            }
        }
    }

    # Execute pipeline through orchestration service
    pipeline_res = await analysis_orchestration_service.execute_analysis_pipeline(
        analysis_id=analysis.id,
        diff_text=diff_text,
        base_files=base_files,
        head_files=head_files,
        coverage_data=coverage_data,
        db=db_session,
    )

    assert pipeline_res["status"] == "COMPLETED"
    assert "summary_markdown" in pipeline_res

    # 1. GET /api/v1/analyses/{id}
    res_overview = await client.get(f"/api/v1/analyses/{analysis.id}")
    assert res_overview.status_code == 200
    overview_data = res_overview.json()
    assert overview_data["status"] == "COMPLETED"
    assert overview_data["risk_tier"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    # 2. GET /api/v1/analyses/{id}/features
    res_feat = await client.get(f"/api/v1/analyses/{analysis.id}/features")
    assert res_feat.status_code == 200
    features = res_feat.json()["features"]
    assert "change_size" in features
    assert "delta_average_complexity" in features

    # 3. GET /api/v1/analyses/{id}/risk
    res_risk = await client.get(f"/api/v1/analyses/{analysis.id}/risk")
    assert res_risk.status_code == 200
    risk_data = res_risk.json()
    assert 0.0 <= risk_data["risk_score"] <= 1.0
    assert len(risk_data["top_risk_factors"]) >= 0

    # 4. GET /api/v1/analyses/{id}/dependencies
    res_deps = await client.get(f"/api/v1/analyses/{analysis.id}/dependencies")
    assert res_deps.status_code == 200
    deps_data = res_deps.json()
    assert "nodes" in deps_data
    assert "edges" in deps_data

    # 5. GET /api/v1/analyses/{id}/recommended-tests
    res_tests = await client.get(f"/api/v1/analyses/{analysis.id}/recommended-tests")
    assert res_tests.status_code == 200
    tests_data = res_tests.json()
    assert tests_data["selected_tests_count"] >= 1
    assert tests_data["time_savings_percent"] >= 0.0

    # 6. GET /api/v1/analyses/{id}/report
    res_report = await client.get(f"/api/v1/analyses/{analysis.id}/report")
    assert res_report.status_code == 200
    report_data = res_report.json()
    assert "CodeImpact" in report_data["summary_markdown"]


async def test_platform_metrics_endpoint(client: AsyncClient):
    # 1. Summary JSON metrics
    resp = await client.get("/api/v1/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_repositories" in data
    assert "risk_tier_distribution" in data
    assert "active_model_name" in data

    # 2. Prometheus exposition
    prom_resp = await client.get("/api/v1/metrics/prometheus")
    assert prom_resp.status_code == 200
    assert b"codeimpact_analyses_total" in prom_resp.content
