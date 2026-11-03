from __future__ import annotations

import os
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.services.github.client import GitHubClient, github_client

logger = get_logger(__name__)


class PathTraversalSecurityError(Exception):
    pass


class RepositorySnapshotService:
    """
    Safely retrieves and manages repository source snapshots and diffs.
    Strictly enforces path sanitization to prevent directory traversal and
    ensures code is analyzed statically in-memory without host execution.
    """

    def __init__(
        self,
        client: GitHubClient | None = None,
        storage_root: str = settings.WORKSPACE_STORAGE_PATH,
    ):
        self.client = client or github_client
        self.storage_root = Path(storage_root)
        os.makedirs(self.storage_root, exist_ok=True)

    def sanitize_relative_path(self, relative_path: str) -> str:
        """
        Validate and sanitize relative file paths extracted from git diffs.
        Rejects directory traversal attempts, absolute paths, or null bytes.
        """
        if not relative_path or not relative_path.strip():
            raise PathTraversalSecurityError("File path cannot be empty")

        if "\x00" in relative_path:
            raise PathTraversalSecurityError("Null bytes detected in path")

        if "\\" in relative_path or ":" in relative_path:
            raise PathTraversalSecurityError(
                f"Backslash or drive path not permitted: {relative_path}"
            )

        # Normalize path
        normalized = os.path.normpath(relative_path.strip())

        if normalized.startswith("/") or normalized.startswith("\\"):
            raise PathTraversalSecurityError(f"Absolute paths not permitted: {relative_path}")

        if (
            normalized == ".."
            or normalized.startswith("../")
            or "/../" in normalized
            or normalized.endswith("/..")
        ):
            raise PathTraversalSecurityError(
                f"Directory traversal sequence detected: {relative_path}"
            )

        return normalized

    async def get_pull_request_diff(
        self, owner: str, repo: str, pr_number: int, installation_id: int | None = None
    ) -> str:
        """
        Fetch unified diff from GitHub API.
        """
        return await self.client.get_pull_request_diff(
            owner=owner, repo=repo, pr_number=pr_number, installation_id=installation_id
        )

    async def get_file_content_at_ref(
        self,
        owner: str,
        repo: str,
        file_path: str,
        ref: str,
        installation_id: int | None = None,
    ) -> str | None:
        """
        Retrieve raw file content at a specific commit SHA or branch ref.
        """
        safe_path = self.sanitize_relative_path(file_path)
        try:
            resp = await self.client._request(
                method="GET",
                path=f"/repos/{owner}/{repo}/contents/{safe_path}",
                params={"ref": ref},
                installation_id=installation_id,
                accept="application/vnd.github.v3.raw",
            )
            return resp.text
        except Exception as e:
            logger.warning(
                f"Could not retrieve file content for {owner}/{repo}:{safe_path} at ref {ref}: {e}"
            )
            return None


snapshot_service = RepositorySnapshotService()
