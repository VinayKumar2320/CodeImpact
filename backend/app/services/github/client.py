from __future__ import annotations

import asyncio
import random
import time
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from app.core.logging import get_logger
from app.schemas.github import GitHubCommitSummary, GitHubFileChange
from app.services.github.auth import GitHubAuthService, github_auth_service

logger = get_logger(__name__)


class GitHubAPIError(Exception):
    def __init__(self, message: str, status_code: int = 500, response_text: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class GitHubRateLimitError(GitHubAPIError):
    pass


class GitHubResourceNotFoundError(GitHubAPIError):
    pass


class GitHubAuthError(GitHubAPIError):
    pass


class GitHubClient:
    """
    Asynchronous HTTP client for interacting with the GitHub REST API (v3).
    Supports installation tokens, automatic exponential backoff with jitter,
    rate limit handling, pagination, and unified error mapping.
    """

    def __init__(
        self,
        auth_service: GitHubAuthService | None = None,
        base_url: str = "https://api.github.com",
        max_retries: int = 3,
        initial_backoff_sec: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.auth_service = auth_service or github_auth_service
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.initial_backoff_sec = initial_backoff_sec
        self.transport = transport

    async def _request(
        self,
        method: str,
        path: str,
        installation_id: int | None = None,
        token: str | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_data: Any | None = None,
        accept: str = "application/vnd.github.v3+json",
    ) -> httpx.Response:
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        req_headers = {
            "Accept": accept,
            "User-Agent": "CodeImpact-ChangeRiskAnalyzer/1.0",
        }
        if headers:
            req_headers.update(headers)

        if token:
            req_headers["Authorization"] = f"token {token}"
        elif installation_id:
            auth_token = await self.auth_service.get_installation_token(installation_id)
            req_headers["Authorization"] = f"token {auth_token}"
        elif self.auth_service.token_fallback:
            req_headers["Authorization"] = f"token {self.auth_service.token_fallback}"

        async with httpx.AsyncClient(timeout=15.0, transport=self.transport) as client:
            retries = 0
            while True:
                try:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=req_headers,
                        params=params,
                        json=json_data,
                    )

                    # Handle successful response
                    if response.status_code in (200, 201, 202, 204):
                        return response

                    # Rate Limiting (403 or 429)
                    if response.status_code in (403, 429):
                        rate_limit_remaining = response.headers.get("x-ratelimit-remaining")
                        if rate_limit_remaining == "0" or "rate limit" in response.text.lower():
                            if retries < self.max_retries:
                                reset_time = response.headers.get("x-ratelimit-reset")
                                wait_sec = (
                                    max(1.0, float(reset_time) - time.time())
                                    if reset_time
                                    else self.initial_backoff_sec * (2**retries)
                                )
                                jitter = random.uniform(0.1, 0.5)
                                backoff = min(wait_sec + jitter, 10.0)
                                logger.warning(
                                    f"GitHub Rate Limit hit on {path}. Retrying in {backoff:.2f}s (retry {retries + 1}/{self.max_retries})"
                                )
                                retries += 1
                                await asyncio.sleep(backoff)
                                continue
                            raise GitHubRateLimitError(
                                f"GitHub API Rate Limit exceeded on {path}",
                                status_code=response.status_code,
                                response_text=response.text,
                            )

                    # 404 Not Found
                    if response.status_code == 404:
                        raise GitHubResourceNotFoundError(
                            f"GitHub resource not found at {path}",
                            status_code=404,
                            response_text=response.text,
                        )

                    # 401 Unauthorized
                    if response.status_code == 401:
                        raise GitHubAuthError(
                            f"GitHub authorization failed on {path}",
                            status_code=401,
                            response_text=response.text,
                        )

                    # 5xx Server Transient Errors -> Exponential Backoff
                    if response.status_code >= 500 and retries < self.max_retries:
                        backoff = self.initial_backoff_sec * (2**retries) + random.uniform(0.1, 0.3)
                        logger.warning(
                            f"GitHub 5xx transient error {response.status_code} on {path}. Retrying in {backoff:.2f}s"
                        )
                        retries += 1
                        await asyncio.sleep(backoff)
                        continue

                    # Unhandled failure
                    raise GitHubAPIError(
                        f"GitHub API error {response.status_code} on {method} {path}: {response.text}",
                        status_code=response.status_code,
                        response_text=response.text,
                    )

                except (httpx.TimeoutException, httpx.NetworkError) as err:
                    if retries < self.max_retries:
                        backoff = self.initial_backoff_sec * (2**retries) + random.uniform(0.1, 0.3)
                        logger.warning(
                            f"Network error communicating with GitHub on {path}: {err}. Retrying in {backoff:.2f}s"
                        )
                        retries += 1
                        await asyncio.sleep(backoff)
                        continue
                    raise GitHubAPIError(
                        f"Network failure calling GitHub API at {path}: {err}",
                        status_code=504,
                    ) from err

    async def get_repository(
        self, owner: str, repo: str, installation_id: int | None = None
    ) -> dict[str, Any]:
        resp = await self._request("GET", f"/repos/{owner}/{repo}", installation_id=installation_id)
        return cast(dict[str, Any], resp.json())

    async def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
        installation_id: int | None = None,
    ) -> list[dict[str, Any]]:
        resp = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls",
            params={"state": state, "per_page": per_page},
            installation_id=installation_id,
        )
        return cast(list[dict[str, Any]], resp.json())

    async def get_pull_request(
        self, owner: str, repo: str, pr_number: int, installation_id: int | None = None
    ) -> dict[str, Any]:
        resp = await self._request(
            "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}", installation_id=installation_id
        )
        return cast(dict[str, Any], resp.json())

    async def get_pull_request_diff(
        self, owner: str, repo: str, pr_number: int, installation_id: int | None = None
    ) -> str:
        """
        Retrieve raw unified git diff representation for a pull request.
        """
        resp = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            installation_id=installation_id,
            accept="application/vnd.github.v3.diff",
        )
        return resp.text

    async def get_pull_request_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        per_page: int = 100,
        installation_id: int | None = None,
    ) -> list[GitHubFileChange]:
        """
        Retrieve all changed files in a pull request with automatic pagination.
        """
        files: list[GitHubFileChange] = []
        page = 1

        while True:
            resp = await self._request(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
                params={"page": page, "per_page": per_page},
                installation_id=installation_id,
            )
            data = resp.json()
            if not data:
                break

            for item in data:
                files.append(
                    GitHubFileChange(
                        filename=item.get("filename", ""),
                        status=item.get("status", "modified"),
                        additions=item.get("additions", 0),
                        deletions=item.get("deletions", 0),
                        changes=item.get("changes", 0),
                        patch=item.get("patch"),
                        raw_url=item.get("raw_url"),
                        previous_filename=item.get("previous_filename"),
                    )
                )

            if len(data) < per_page:
                break
            page += 1

        return files

    async def get_commit_history(
        self,
        owner: str,
        repo: str,
        sha: str,
        path: str | None = None,
        per_page: int = 50,
        installation_id: int | None = None,
    ) -> list[GitHubCommitSummary]:
        """
        Retrieve recent commit history for a repository or specific path.
        """
        params: dict[str, Any] = {"sha": sha, "per_page": per_page}
        if path:
            params["path"] = path

        resp = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/commits",
            params=params,
            installation_id=installation_id,
        )
        data = resp.json()
        summaries: list[GitHubCommitSummary] = []
        for item in data:
            commit_data = item.get("commit", {})
            author_data = commit_data.get("author", {})
            timestamp_str = author_data.get("date")
            dt = (
                datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                if timestamp_str
                else datetime.now(UTC)
            )

            summaries.append(
                GitHubCommitSummary(
                    sha=item.get("sha", ""),
                    author_name=author_data.get("name", "Unknown"),
                    author_email=author_data.get("email"),
                    message=commit_data.get("message", ""),
                    timestamp=dt,
                )
            )
        return summaries

    async def create_check_run(
        self,
        owner: str,
        repo: str,
        name: str,
        head_sha: str,
        status: str = "in_progress",
        conclusion: str | None = None,
        output: dict[str, Any] | None = None,
        installation_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Publish or update a GitHub Check Run.
        """
        body: dict[str, Any] = {
            "name": name,
            "head_sha": head_sha,
            "status": status,
        }
        if conclusion:
            body["conclusion"] = conclusion
            body["completed_at"] = datetime.now(UTC).isoformat()
        if output:
            body["output"] = output

        resp = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/check-runs",
            json_data=body,
            installation_id=installation_id,
        )
        return cast(dict[str, Any], resp.json())


github_client = GitHubClient()
