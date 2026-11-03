from __future__ import annotations

import httpx
import pytest

from app.services.github.auth import GitHubAuthService
from app.services.github.client import (
    GitHubAuthError,
    GitHubClient,
    GitHubRateLimitError,
    GitHubResourceNotFoundError,
)


@pytest.mark.asyncio
async def test_github_client_get_pull_request_success():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octocat/Hello-World/pulls/42"
        return httpx.Response(
            200,
            json={
                "id": 100042,
                "number": 42,
                "title": "Fix memory leak in buffer pool",
                "state": "open",
            },
        )

    auth = GitHubAuthService(token_fallback="mock_pat")
    client = GitHubClient(auth_service=auth, transport=httpx.MockTransport(mock_handler))
    pr_data = await client.get_pull_request("octocat", "Hello-World", 42)
    assert pr_data["number"] == 42
    assert pr_data["title"] == "Fix memory leak in buffer pool"


@pytest.mark.asyncio
async def test_github_client_not_found_raises():
    def mock_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    client = GitHubClient(
        auth_service=GitHubAuthService(token_fallback="mock"),
        transport=httpx.MockTransport(mock_handler),
    )
    with pytest.raises(GitHubResourceNotFoundError):
        await client.get_repository("octocat", "nonexistent-repo")


@pytest.mark.asyncio
async def test_github_client_unauthorized_raises():
    def mock_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    client = GitHubClient(
        auth_service=GitHubAuthService(token_fallback="mock"),
        transport=httpx.MockTransport(mock_handler),
    )
    with pytest.raises(GitHubAuthError):
        await client.get_repository("octocat", "private-repo")


@pytest.mark.asyncio
async def test_github_client_rate_limiting_retry_and_exhaustion():
    call_count = 0

    def mock_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            403,
            headers={"x-ratelimit-remaining": "0"},
            json={"message": "API rate limit exceeded"},
        )

    client = GitHubClient(
        auth_service=GitHubAuthService(token_fallback="mock"),
        max_retries=2,
        initial_backoff_sec=0.01,
        transport=httpx.MockTransport(mock_handler),
    )
    with pytest.raises(GitHubRateLimitError):
        await client.get_pull_request("octocat", "repo", 1)

    assert call_count == 3  # Initial + 2 retries


@pytest.mark.asyncio
async def test_github_client_files_pagination():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", 1))
        if page == 1:
            return httpx.Response(
                200,
                json=[
                    {
                        "filename": "app/main.py",
                        "status": "modified",
                        "additions": 10,
                        "deletions": 2,
                    },
                    {"filename": "app/auth.py", "status": "added", "additions": 35, "deletions": 0},
                ],
            )
        elif page == 2:
            return httpx.Response(
                200,
                json=[
                    {
                        "filename": "tests/test_auth.py",
                        "status": "added",
                        "additions": 25,
                        "deletions": 0,
                    },
                ],
            )
        else:
            return httpx.Response(200, json=[])

    client = GitHubClient(
        auth_service=GitHubAuthService(token_fallback="mock"),
        transport=httpx.MockTransport(mock_handler),
    )
    # 2 pages returned with per_page=2
    files = await client.get_pull_request_files("octocat", "repo", 10, per_page=2)
    assert len(files) == 3
    assert files[0].filename == "app/main.py"
    assert files[2].filename == "tests/test_auth.py"
