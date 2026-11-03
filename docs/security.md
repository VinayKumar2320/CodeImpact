# Security Architecture & Hardening Standards

## 1. Threat Model & Security Posture
CodeImpact ingests untrusted pull request code, webhook payloads, and diff content from public and private GitHub repositories. To prevent arbitrary remote code execution (RCE), token theft, and path traversal vulnerabilities, CodeImpact enforces strict isolation boundaries across all subsystems.

```
[Untrusted GitHub Pull Request]
          |
          v
[HMAC-SHA256 Verification] ---> [Payload Sanitization]
                                          |
                                          v
                              [Tree-sitter AST Parser]
                              (Pure Static Analysis - NO EXECUTION)
                                          |
                                          v
                              [Feature Vector & Model]
```

---

## 2. Core Security Controls

### A. Untrusted Code Non-Execution Principle
- **Zero Host Execution**: The application server **never** imports, runs, executes, or evaluates untrusted pull request code or tests.
- **Pure Abstract Syntax Tree (AST) Parsing**: Analysis is conducted strictly via Tree-sitter binary grammar parsers that operate directly on raw text streams into AST node tokens. Python `eval()`, `exec()`, or dynamic module importing (`importlib`) is strictly forbidden on repository code.
- **Isolated CI Metadata**: Test coverage and duration measurements are collected from trusted CI artifact reports (e.g. pytest coverage JSON) rather than executing tests directly on the application host.

### B. Timing-Safe Webhook HMAC-SHA256 Verification
GitHub webhooks are authenticated via HMAC-SHA256 signatures passed in `X-Hub-Signature-256`. Signatures are evaluated in constant time using `hmac.compare_digest` to prevent timing-attack side channels:

```python
def verify_github_signature(payload_bytes: bytes, signature_header: str | None, secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)
```

### C. Path Traversal & Directory Sanitization
Repository snapshots and diff file paths are treated as untrusted input. The `RepositorySnapshotService` strictly sanitizes all paths:

```python
def sanitize_relative_path(self, relative_path: str) -> str:
    # Reject null bytes, backslashes, absolute prefixes, and drive letters
    if "\x00" in relative_path or "\\" in relative_path or ":" in relative_path:
        raise PathTraversalSecurityError("Invalid path characters detected")
    norm = os.path.normpath(relative_path).replace("\\", "/")
    if norm.startswith(("../", "..")) or os.path.isabs(norm):
        raise PathTraversalSecurityError("Path traversal escape attempted")
    return norm
```
Fuzzed against canonical attack patterns: `../../etc/passwd`, `../..//etc/shadow`, `/var/run/docker.sock`, and null byte injection `\x00malicious.py`.

### D. GitHub App Token Isolation & Least Privilege
- **No Broad Personal Access Tokens**: GitHub App installation authentication generates short-lived (1-hour) installation access tokens scoped strictly to registered repositories.
- **Token Isolation**: GitHub API tokens and secrets are strictly retained in backend memory and environment variables. Tokens are **never** returned in API responses, serialized into database tables, or transmitted to the React frontend.

### E. Rate Limiting, Retries & Exponential Backoff
- Outgoing GitHub REST API calls utilize `tenacity` retry decorators with exponential backoff and randomized jitter to prevent rate-limit exhaustion.
- Incoming webhook delivery IDs (`X-GitHub-Delivery`) are recorded with a 24-hour TTL in Redis (`SETNX`) to ensure idempotency and eliminate duplicate analysis storms.

---

## 3. Automated Security Verification Suite

Run the automated security regression test suite:
```bash
pytest backend/tests/security/test_security_hardening.py -v
```
All 15 security tests validate timing safety, path traversal denial, corrupted diff resilience, and token non-exposure.
