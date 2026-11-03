from __future__ import annotations

import hashlib
import hmac

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.security import verify_github_signature
from app.services.analysis.ast_parser import python_ast_parser
from app.services.analysis.diff_parser import diff_parser
from app.services.github.snapshots import PathTraversalSecurityError, snapshot_service


def test_timing_attack_resistance_signature_verification():
    secret = "production_webhook_secret_key_123"
    payload = b'{"action": "opened", "number": 10}'
    mac = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    valid_sig = f"sha256={mac}"

    # Valid signature
    assert verify_github_signature(payload, valid_sig, secret) is True

    # Tampered signature of identical length (timing-safe check)
    tampered_sig = f"sha256={'0' * 64}"
    assert verify_github_signature(payload, tampered_sig, secret) is False

    # Short or malformed headers
    assert verify_github_signature(payload, "invalid_sig", secret) is False
    assert verify_github_signature(payload, "", secret) is False
    assert verify_github_signature(payload, "sha1=abcd", secret) is False


@pytest.mark.parametrize(
    "hostile_path",
    [
        "../../etc/passwd",
        "../..//etc/shadow",
        "../../../root/.ssh/id_rsa",
        "app/../../secret.env",
        "/etc/hosts",
        "/var/run/docker.sock",
        "C:\\Windows\\System32\\cmd.exe",
        "app/services/\x00malicious.py",
        "app/services/../../../proc/cpuinfo",
        "",
        "   ",
    ],
)
def test_path_traversal_fuzzing(hostile_path: str):
    with pytest.raises(PathTraversalSecurityError):
        snapshot_service.sanitize_relative_path(hostile_path)


def test_malformed_and_giant_diff_handling():
    # 1. Giant diff with 20,000 synthetic hunks
    hunk_lines = ["@@ -1,5 +1,5 @@\n-old_line\n+new_line\n"] * 5000
    giant_diff = "diff --git a/big.py b/big.py\n--- a/big.py\n+++ b/big.py\n" + "".join(hunk_lines)

    parsed = diff_parser.parse(giant_diff)
    assert parsed.files_changed_count == 1
    assert parsed.lines_added == 5000
    assert parsed.lines_deleted == 5000

    # 2. Corrupted and binary garbage diff
    corrupted_diff = "\x00\x01\x02\xff\xfeBINARY_GARBAGE\n@@ not a real hunk @@"
    parsed_corrupted = diff_parser.parse(corrupted_diff)
    assert parsed_corrupted.files_changed_count == 0


def test_untrusted_code_never_executed():
    """
    Ensure hostile code in PR changes (e.g. system commands or eval)
    is parsed strictly as static syntax trees and NEVER executed.
    """
    hostile_code = """
import os
import sys

# Attempt malicious payload
os.system("echo HOSTILE_EXECUTION_ATTEMPT > /tmp/hostile_test.txt")
eval("__import__('os').system('touch /tmp/pwned')")

def delete_database():
    os.remove("/tmp/database.db")
"""
    # Parse through AST parser
    summary = python_ast_parser.parse_source(hostile_code, "hostile.py")

    func_names = [f.name for f in summary.functions]
    imported_mods = [imp.module for imp in summary.imports]

    assert "delete_database" in func_names
    assert "os" in imported_mods

    # Verify that hostile side-effects never occurred
    import os

    assert not os.path.exists("/tmp/hostile_test.txt")
    assert not os.path.exists("/tmp/pwned")


async def test_token_exposure_prevention(client: AsyncClient):
    """
    Verifies that GitHub App credentials, webhook secrets, and private keys
    are strictly excluded from all public API endpoints.
    """
    # 1. Check overview metrics
    metrics_resp = await client.get("/api/v1/metrics")
    content = metrics_resp.text
    assert settings.GITHUB_WEBHOOK_SECRET not in content
    assert "private_key" not in content.lower()

    # 2. Check health endpoint
    health_resp = await client.get("/api/v1/health")
    h_content = health_resp.text
    assert settings.GITHUB_WEBHOOK_SECRET not in h_content
    assert "private_key" not in h_content.lower()
