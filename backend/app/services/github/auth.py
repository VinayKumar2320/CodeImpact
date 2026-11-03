from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta

import httpx
import jwt

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class GitHubAuthService:
    """
    Handles GitHub App JWT generation, installation access tokens, and caching.
    Provides graceful fallback for testing and development environments.
    """

    def __init__(
        self,
        app_id: str | None = None,
        private_key: str | None = None,
        token_fallback: str | None = None,
    ):
        self.app_id = app_id or settings.GITHUB_APP_ID
        self.private_key = private_key or settings.GITHUB_APP_PRIVATE_KEY
        self.token_fallback = token_fallback or os.environ.get("GITHUB_TOKEN", "")
        self._installation_tokens: dict[int, tuple[str, datetime]] = {}

    def is_app_configured(self) -> bool:
        return bool(self.app_id and self.private_key)

    def generate_app_jwt(self, expiration_seconds: int = 540) -> str:
        """
        Generate an RS256 JWT for GitHub App authentication.
        Valid for up to 10 minutes.
        """
        if not self.is_app_configured():
            raise ValueError("GitHub App ID and Private Key must be configured to generate App JWT")

        now = int(time.time())
        payload = {
            "iat": now - 60,  # 1 minute clock drift allowance
            "exp": now + expiration_seconds,
            "iss": self.app_id,
        }

        # Handle raw PEM string or path to key file
        key_content = self.private_key
        if key_content.startswith("/") and os.path.exists(key_content):
            with open(key_content) as f:
                key_content = f.read()

        return jwt.encode(payload, key_content, algorithm="RS256")

    async def get_installation_token(self, installation_id: int) -> str:
        """
        Retrieve a valid installation access token, using in-memory cache if not expired.
        Falls back to GITHUB_TOKEN or mock token if GitHub App credentials are not provided.
        """
        # Check cache
        if installation_id in self._installation_tokens:
            token, expiry = self._installation_tokens[installation_id]
            if expiry > datetime.now(UTC) + timedelta(minutes=5):
                return token

        # Fallback to configured token if App credentials missing
        if not self.is_app_configured():
            logger.info(
                f"GitHub App not fully configured. Using fallback token for installation {installation_id}"
            )
            return self.token_fallback or "gh_mock_test_token"

        jwt_token = self.generate_app_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers=headers,
            )
            if resp.status_code != 201:
                logger.error(
                    f"Failed to fetch installation token for {installation_id}: {resp.status_code} {resp.text}"
                )
                raise RuntimeError(
                    f"GitHub API error fetching installation token: HTTP {resp.status_code}"
                )

            data = resp.json()
            token = str(data["token"])
            expires_at_str = str(data["expires_at"])
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))

            self._installation_tokens[installation_id] = (token, expires_at)
            return token


github_auth_service = GitHubAuthService()
