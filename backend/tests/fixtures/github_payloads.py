from __future__ import annotations

from typing import Any

SAMPLE_DIFF_CONTENT = """diff --git a/app/auth.py b/app/auth.py
index e69de29..b2d071c 100644
--- a/app/auth.py
+++ b/app/auth.py
@@ -10,6 +10,12 @@ def authenticate_user(username, password):
     return None

+def validate_session_token(token: str) -> bool:
+    if not token or len(token) < 16:
+        return False
+    return True
+
 def logout(user_id):
     pass
"""


def get_sample_pr_opened_payload(
    pr_number: int = 101,
    head_sha: str = "1111111111111111111111111111111111111111",
    base_sha: str = "0000000000000000000000000000000000000000",
    repo_name: str = "sample-repo",
    repo_owner: str = "octocat",
) -> dict[str, Any]:
    return {
        "action": "opened",
        "number": pr_number,
        "pull_request": {
            "id": 98765000 + pr_number,
            "number": pr_number,
            "title": f"Feature change for PR #{pr_number}",
            "state": "open",
            "user": {
                "id": 12345,
                "login": "octocat",
                "type": "User",
            },
            "head": {
                "sha": head_sha,
                "ref": "feature/security-tokens",
            },
            "base": {
                "sha": base_sha,
                "ref": "main",
            },
            "merged_at": None,
            "draft": False,
        },
        "repository": {
            "id": 54321000,
            "name": repo_name,
            "full_name": f"{repo_owner}/{repo_name}",
            "owner": {
                "id": 12345,
                "login": repo_owner,
            },
            "default_branch": "main",
            "private": False,
        },
        "sender": {
            "id": 12345,
            "login": "octocat",
        },
        "installation": {
            "id": 998877,
        },
    }


def get_sample_pr_synchronize_payload(
    pr_number: int = 101,
    new_head_sha: str = "2222222222222222222222222222222222222222",
    base_sha: str = "0000000000000000000000000000000000000000",
    repo_name: str = "sample-repo",
    repo_owner: str = "octocat",
) -> dict[str, Any]:
    payload = get_sample_pr_opened_payload(
        pr_number=pr_number,
        head_sha=new_head_sha,
        base_sha=base_sha,
        repo_name=repo_name,
        repo_owner=repo_owner,
    )
    payload["action"] = "synchronize"
    return payload


def get_sample_pr_closed_payload(
    pr_number: int = 101,
    merged: bool = True,
    repo_name: str = "sample-repo",
    repo_owner: str = "octocat",
) -> dict[str, Any]:
    payload = get_sample_pr_opened_payload(
        pr_number=pr_number,
        repo_name=repo_name,
        repo_owner=repo_owner,
    )
    payload["action"] = "closed"
    if merged:
        payload["pull_request"]["merged_at"] = "2026-11-03T12:00:00Z"
        payload["pull_request"]["state"] = "closed"
    return payload
