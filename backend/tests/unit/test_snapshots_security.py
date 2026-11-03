from __future__ import annotations

import pytest

from app.services.github.snapshots import (
    PathTraversalSecurityError,
    RepositorySnapshotService,
)


def test_sanitize_relative_path_valid():
    svc = RepositorySnapshotService()
    assert svc.sanitize_relative_path("src/core/main.py") == "src/core/main.py"
    assert svc.sanitize_relative_path("./backend/app/auth.py") == "backend/app/auth.py"
    assert svc.sanitize_relative_path("tests/unit/test_api.py") == "tests/unit/test_api.py"


@pytest.mark.parametrize(
    "hostile_path",
    [
        "../etc/passwd",
        "../../secrets.env",
        "app/../../etc/shadow",
        "app/../..",
        "/etc/passwd",
        "/root/.ssh/id_rsa",
        "\\Windows\\System32",
        "src/auth.py\x00.exe",
        "",
    ],
)
def test_sanitize_relative_path_rejects_hostile_inputs(hostile_path):
    svc = RepositorySnapshotService()
    with pytest.raises(PathTraversalSecurityError):
        svc.sanitize_relative_path(hostile_path)
