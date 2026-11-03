from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services.github.auth import GitHubAuthService


@pytest.fixture(scope="module")
def rsa_key_pair():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    pem_public = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    return pem_private, pem_public


def test_generate_app_jwt_validity(rsa_key_pair):
    pem_private, pem_public = rsa_key_pair
    auth_service = GitHubAuthService(app_id="123456", private_key=pem_private)

    token = auth_service.generate_app_jwt(expiration_seconds=300)
    assert token is not None

    # Verify signature and payload using public key
    decoded = jwt.decode(token, pem_public, algorithms=["RS256"])
    assert decoded["iss"] == "123456"
    assert "iat" in decoded
    assert "exp" in decoded
    assert decoded["exp"] > time.time()


def test_missing_app_configuration_raises_error():
    auth_service = GitHubAuthService(app_id="", private_key="")
    assert auth_service.is_app_configured() is False
    with pytest.raises(ValueError, match="GitHub App ID and Private Key must be configured"):
        auth_service.generate_app_jwt()


@pytest.mark.asyncio
async def test_get_installation_token_fallback():
    auth_service = GitHubAuthService(app_id="", private_key="", token_fallback="test_token_xyz")
    token = await auth_service.get_installation_token(998877)
    assert token == "test_token_xyz"
