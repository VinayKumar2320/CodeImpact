from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_github_signature
from app.models.analysis import Analysis
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.services.github.webhook_handler import webhook_handler
from tests.fixtures.github_payloads import (
    get_sample_pr_closed_payload,
    get_sample_pr_opened_payload,
    get_sample_pr_synchronize_payload,
)


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(client: AsyncClient):
    payload = json.dumps({"action": "opened"}).encode("utf-8")
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": "sha256=invalidhexsignature000000000000000000000000",
        "X-GitHub-Delivery": "del-invalid-sig-001",
    }
    response = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
    assert response.status_code == 401
    assert "Invalid GitHub webhook signature" in response.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_pr_opened_end_to_end(client: AsyncClient, db_session: AsyncSession):
    payload_dict = get_sample_pr_opened_payload(pr_number=50, head_sha="a" * 40, base_sha="b" * 40)
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = generate_github_signature(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)
    delivery_id = "del-opened-pr-050"

    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": sig,
        "X-GitHub-Delivery": delivery_id,
        "Content-Type": "application/json",
    }

    response = await client.post("/api/v1/webhooks/github", content=payload_bytes, headers=headers)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["event"] == "pull_request"
    assert data["action"] == "opened"
    assert data["pr_number"] == 50
    assert data["analysis_id"] is not None

    # Verify DB records
    stmt_repo = select(Repository).where(Repository.name == "sample-repo")
    res_repo = await db_session.execute(stmt_repo)
    repo = res_repo.scalar_one_or_none()
    assert repo is not None
    assert repo.owner == "octocat"

    stmt_pr = select(PullRequest).where(PullRequest.pr_number == 50)
    res_pr = await db_session.execute(stmt_pr)
    pr = res_pr.scalar_one_or_none()
    assert pr is not None
    assert pr.head_sha == "a" * 40
    assert pr.state == "open"

    stmt_analysis = select(Analysis).where(Analysis.id == data["analysis_id"])
    res_analysis = await db_session.execute(stmt_analysis)
    analysis = res_analysis.scalar_one_or_none()
    assert analysis is not None
    assert analysis.commit_sha == "a" * 40
    assert analysis.status == "PENDING"


@pytest.mark.asyncio
async def test_webhook_delivery_deduplication(client: AsyncClient, db_session: AsyncSession):
    payload_dict = get_sample_pr_opened_payload(pr_number=51, head_sha="c" * 40)
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = generate_github_signature(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)
    delivery_id = "del-dedupe-test-051"

    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": sig,
        "X-GitHub-Delivery": delivery_id,
        "Content-Type": "application/json",
    }

    # Mock Redis deduplication in webhook_handler
    processed_deliveries = set()

    def mock_dedupe(did: str | None) -> bool:
        if did in processed_deliveries:
            return False
        if did:
            processed_deliveries.add(did)
        return True

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(webhook_handler, "check_and_record_delivery", mock_dedupe)

        # First delivery -> Accepted (202)
        resp1 = await client.post("/api/v1/webhooks/github", content=payload_bytes, headers=headers)
        assert resp1.status_code == 202
        assert resp1.json()["status"] == "accepted"

        # Duplicate delivery with identical delivery ID -> Duplicate (200)
        resp2 = await client.post("/api/v1/webhooks/github", content=payload_bytes, headers=headers)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "duplicate"
        assert "Duplicate delivery" in resp2.json()["message"]

    # Verify that only 1 analysis record was created for PR #51
    stmt = select(Analysis).join(PullRequest).where(PullRequest.pr_number == 51)
    res = await db_session.execute(stmt)
    analyses = res.scalars().all()
    assert len(analyses) == 1


@pytest.mark.asyncio
async def test_webhook_pr_synchronize_supersedes_outdated_analysis(
    client: AsyncClient, db_session: AsyncSession
):
    pr_number = 52
    sha_1 = "1" * 40
    sha_2 = "2" * 40

    # 1. First commit: PR opened
    payload_open = get_sample_pr_opened_payload(pr_number=pr_number, head_sha=sha_1)
    bytes_open = json.dumps(payload_open).encode("utf-8")
    sig_open = generate_github_signature(bytes_open, settings.GITHUB_WEBHOOK_SECRET)
    headers_open = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": sig_open,
        "X-GitHub-Delivery": "del-sync-step-1",
        "Content-Type": "application/json",
    }
    resp1 = await client.post("/api/v1/webhooks/github", content=bytes_open, headers=headers_open)
    assert resp1.status_code == 202
    analysis_1_id = resp1.json()["analysis_id"]

    # 2. Second commit: PR synchronize
    payload_sync = get_sample_pr_synchronize_payload(pr_number=pr_number, new_head_sha=sha_2)
    bytes_sync = json.dumps(payload_sync).encode("utf-8")
    sig_sync = generate_github_signature(bytes_sync, settings.GITHUB_WEBHOOK_SECRET)
    headers_sync = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": sig_sync,
        "X-GitHub-Delivery": "del-sync-step-2",
        "Content-Type": "application/json",
    }
    resp2 = await client.post("/api/v1/webhooks/github", content=bytes_sync, headers=headers_sync)
    assert resp2.status_code == 202
    analysis_2_id = resp2.json()["analysis_id"]

    assert analysis_1_id != analysis_2_id

    # Verify that analysis 1 status was updated to SUPERSEDED
    stmt1 = select(Analysis).where(Analysis.id == analysis_1_id)
    res1 = await db_session.execute(stmt1)
    a1 = res1.scalar_one()
    assert a1.status == "SUPERSEDED"
    assert "Superseded" in (a1.error_message or "")

    # Verify that analysis 2 is PENDING with head SHA sha_2
    stmt2 = select(Analysis).where(Analysis.id == analysis_2_id)
    res2 = await db_session.execute(stmt2)
    a2 = res2.scalar_one()
    assert a2.status == "PENDING"
    assert a2.commit_sha == sha_2


@pytest.mark.asyncio
async def test_webhook_pr_closed(client: AsyncClient, db_session: AsyncSession):
    pr_number = 53
    # Open PR first
    payload_open = get_sample_pr_opened_payload(pr_number=pr_number)
    bytes_open = json.dumps(payload_open).encode("utf-8")
    sig_open = generate_github_signature(bytes_open, settings.GITHUB_WEBHOOK_SECRET)
    headers_open = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": sig_open,
        "X-GitHub-Delivery": "del-closed-test-open",
        "Content-Type": "application/json",
    }
    await client.post("/api/v1/webhooks/github", content=bytes_open, headers=headers_open)

    # Now close PR
    payload_closed = get_sample_pr_closed_payload(pr_number=pr_number, merged=True)
    bytes_closed = json.dumps(payload_closed).encode("utf-8")
    sig_closed = generate_github_signature(bytes_closed, settings.GITHUB_WEBHOOK_SECRET)
    headers_closed = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": sig_closed,
        "X-GitHub-Delivery": "del-closed-test-close",
        "Content-Type": "application/json",
    }
    resp = await client.post(
        "/api/v1/webhooks/github", content=bytes_closed, headers=headers_closed
    )
    assert resp.status_code == 202
    assert resp.json()["action"] == "closed"

    # Verify PR state in DB
    stmt = select(PullRequest).where(PullRequest.pr_number == pr_number)
    res = await db_session.execute(stmt)
    pr = res.scalar_one()
    assert pr.state == "closed"
    assert pr.merged_at is not None
