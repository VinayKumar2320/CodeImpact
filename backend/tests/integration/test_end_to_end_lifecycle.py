from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.analysis import Analysis, AnalysisStatus
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.services.analysis.orchestration_service import analysis_orchestration_service
from app.services.github.webhook_handler import webhook_handler
from app.services.reporting.check_runs import check_run_publisher


async def test_complete_platform_lifecycle_and_failure_resilience(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Validates end-to-end workflow:
    Webhook intake -> Verification -> Queue -> Static Analysis -> ML Prediction ->
    Test Selection -> Persistence -> Check Run -> REST API.
    """
    secret = settings.GITHUB_WEBHOOK_SECRET

    processed_deliveries = set()

    def mock_dedupe(did: str | None) -> bool:
        if did in processed_deliveries:
            return False
        if did:
            processed_deliveries.add(did)
        return True

    monkeypatch.setattr(webhook_handler, "check_and_record_delivery", mock_dedupe)

    # Step 1: Simulate GitHub Webhook (pull_request.opened)
    delivery_id = str(uuid.uuid4())
    webhook_payload = {
        "action": "opened",
        "repository": {
            "id": 998877,
            "name": "payments-core",
            "full_name": "fintech/payments-core",
            "owner": {"login": "fintech"},
            "default_branch": "main",
        },
        "pull_request": {
            "id": 554433,
            "number": 108,
            "title": "Refactor payment checkout gateway and retry policy",
            "state": "open",
            "user": {"login": "senior-eng"},
            "head": {"sha": "head_checkout_abc123", "ref": "feature/checkout-v2"},
            "base": {"sha": "base_checkout_000000", "ref": "main"},
        },
    }

    raw_payload = json.dumps(webhook_payload).encode("utf-8")
    sig = f"sha256={hmac.new(secret.encode('utf-8'), raw_payload, hashlib.sha256).hexdigest()}"

    headers = {
        "X-GitHub-Delivery": delivery_id,
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": sig,
        "Content-Type": "application/json",
    }

    # Post webhook
    resp = await client.post("/api/v1/webhooks/github", content=raw_payload, headers=headers)
    assert resp.status_code == 202
    webhook_res = resp.json()
    assert webhook_res["status"] == "accepted"

    # Step 2: Test Deduplication (resend identical delivery ID)
    dup_resp = await client.post("/api/v1/webhooks/github", content=raw_payload, headers=headers)
    assert dup_resp.status_code == 200
    assert dup_resp.json()["status"] == "duplicate"

    # Step 3: Verify Repository and PullRequest persisted
    repo = (
        await db_session.execute(
            select(Repository).where(Repository.full_name == "fintech/payments-core")
        )
    ).scalar_one()
    assert repo.full_name == "fintech/payments-core"

    pr = (
        await db_session.execute(select(PullRequest).where(PullRequest.repository_id == repo.id))
    ).scalar_one()
    assert pr.pr_number == 108

    # Step 4: Run Static Analysis + ML Risk Prediction + Test Selection
    analysis_id = str(uuid.uuid4())
    analysis = Analysis(
        id=analysis_id,
        pull_request_id=pr.id,
        commit_sha=pr.head_sha,
        base_sha=pr.base_sha,
        status=AnalysisStatus.QUEUED.value,
        analysis_version="1.0.0",
    )
    db_session.add(analysis)
    await db_session.commit()

    diff_text = """diff --git a/services/gateway.py b/services/gateway.py
index 1000000..2000000 100644
--- a/services/gateway.py
+++ b/services/gateway.py
@@ -15,4 +15,10 @@ def process_payment(amount, token):
+    if amount <= 0:
+        raise ValueError("Invalid amount")
+    for retry in range(3):
+        if token.is_valid():
+            return True
+    return False
"""
    base_files = {
        "services/gateway.py": "def process_payment(amount, token):\n    return True\n",
    }
    head_files = {
        "services/gateway.py": (
            "def process_payment(amount, token):\n"
            "    if amount <= 0:\n"
            "        raise ValueError('Invalid amount')\n"
            "    for retry in range(3):\n"
            "        if token.is_valid():\n"
            "            return True\n"
            "    return False\n"
        ),
        "tests/test_gateway.py": (
            "from services.gateway import process_payment\n"
            "def test_process_payment_success():\n"
            "    assert process_payment(100, None) is False\n"
        ),
    }

    pipeline_result = await analysis_orchestration_service.execute_analysis_pipeline(
        analysis_id=analysis.id,
        diff_text=diff_text,
        base_files=base_files,
        head_files=head_files,
        coverage_data={"files": {"services/gateway.py": {"executed_lines": [15, 16, 17]}}},
        db=db_session,
    )

    assert pipeline_result["status"] == "COMPLETED"

    # Step 5: Check Database Persistence
    stmt = (
        select(Analysis)
        .options(selectinload(Analysis.prediction), selectinload(Analysis.recommended_tests))
        .where(Analysis.id == analysis.id)
    )
    stored_analysis = (await db_session.execute(stmt)).scalar_one()
    assert stored_analysis.status == AnalysisStatus.COMPLETED.value
    assert stored_analysis.prediction is not None
    assert stored_analysis.prediction.risk_tier in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert len(stored_analysis.recommended_tests) >= 1

    # Step 6: Verify Check Run publishing
    check_payload = check_run_publisher.format_check_run_payload(
        prediction=stored_analysis.prediction,  # type: ignore
        test_plan=pipeline_result["test_selection"],  # type: ignore
        static_result=pipeline_result["static_analysis"],
        head_sha=pr.head_sha,
    )
    assert "Risk:" in check_payload["output"]["title"]

    # Step 7: Verify REST API Consumption
    rep_resp = await client.get(f"/api/v1/analyses/{analysis.id}/report")
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    assert rep_data["status"] == "COMPLETED"
    assert "summary_markdown" in rep_data

    # Step 8: Verify Edge Case: PR Synchronize marks older analysis SUPERSEDED
    sync_delivery_id = str(uuid.uuid4())
    sync_payload = dict(webhook_payload)
    sync_payload["action"] = "synchronize"
    sync_payload["pull_request"]["head"]["sha"] = "head_checkout_def456"

    raw_sync = json.dumps(sync_payload).encode("utf-8")
    sync_sig = f"sha256={hmac.new(secret.encode('utf-8'), raw_sync, hashlib.sha256).hexdigest()}"
    sync_headers = {
        "X-GitHub-Delivery": sync_delivery_id,
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": sync_sig,
        "Content-Type": "application/json",
    }

    res_sync = await client.post("/api/v1/webhooks/github", content=raw_sync, headers=sync_headers)
    assert res_sync.status_code == 202

    # In-flight/pending analysis must be marked SUPERSEDED
    initial_analysis = await db_session.get(Analysis, webhook_res["analysis_id"])
    assert initial_analysis is not None
    assert initial_analysis.status == AnalysisStatus.SUPERSEDED.value

    # Prior completed analysis remains preserved as completed historical record
    await db_session.refresh(stored_analysis)
    assert stored_analysis.status == AnalysisStatus.COMPLETED.value
