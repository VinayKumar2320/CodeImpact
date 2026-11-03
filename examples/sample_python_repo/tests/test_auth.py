from auth import authenticate_user, hash_password, validate_session_token

def test_hash_password():
    h = hash_password("secret123")
    assert len(h) == 64

def test_validate_session_token():
    assert validate_session_token("valid_token_longer_than_16_chars") is True
    assert validate_session_token("short") is False

def test_authenticate_user():
    h = hash_password("secret123")
    assert authenticate_user("octocat", h) is True
    assert authenticate_user("", h) is False
