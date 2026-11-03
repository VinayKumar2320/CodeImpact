import hashlib
import hmac


def verify_github_signature(payload: bytes, signature_header: str | None, secret: str) -> bool:
    """
    Verify that the payload matches the GitHub SHA-256 HMAC signature.
    Signature format: sha256=<hex_digest>
    """
    if not signature_header or not secret:
        return False

    parts = signature_header.split("=", 1)
    if len(parts) != 2 or parts[0] != "sha256":
        return False

    expected_signature = parts[1].strip()
    mac = hmac.new(secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
    computed_signature = mac.hexdigest()

    return hmac.compare_digest(computed_signature, expected_signature)


def generate_github_signature(payload: bytes, secret: str) -> str:
    """
    Helper for test suites: compute GitHub sha256 header.
    """
    mac = hmac.new(secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"
