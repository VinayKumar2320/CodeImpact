from app.core.security import generate_github_signature, verify_github_signature


def test_valid_github_signature_verification():
    secret = "my_super_secret_webhook_key"
    payload = b'{"action":"opened","pull_request":{"id":12345}}'
    signature_header = generate_github_signature(payload, secret)

    assert signature_header.startswith("sha256=")
    assert verify_github_signature(payload, signature_header, secret) is True


def test_tampered_payload_fails_signature_verification():
    secret = "my_super_secret_webhook_key"
    payload = b'{"action":"opened","pull_request":{"id":12345}}'
    tampered_payload = b'{"action":"opened","pull_request":{"id":99999}}'
    signature_header = generate_github_signature(payload, secret)

    assert verify_github_signature(tampered_payload, signature_header, secret) is False


def test_invalid_secret_fails_signature_verification():
    secret = "my_super_secret_webhook_key"
    wrong_secret = "attacker_secret"
    payload = b'{"action":"opened"}'
    signature_header = generate_github_signature(payload, secret)

    assert verify_github_signature(payload, signature_header, wrong_secret) is False


def test_missing_or_malformed_signature_header():
    secret = "my_super_secret_webhook_key"
    payload = b'{"action":"opened"}'

    assert verify_github_signature(payload, None, secret) is False
    assert verify_github_signature(payload, "", secret) is False
    assert verify_github_signature(payload, "invalid_no_sha_prefix", secret) is False
