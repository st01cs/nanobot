import pytest
from nanobot.channels.web.auth import AuthManager, TokenData

def test_create_access_token():
    auth = AuthManager(secret="test-secret")
    token = auth.create_access_token(user_id="user-123", username="testuser")
    assert isinstance(token, str)
    assert len(token) > 50  # JWT tokens are long

def test_verify_access_token():
    auth = AuthManager(secret="test-secret")
    token = auth.create_access_token(user_id="user-123", username="testuser")
    payload = auth.verify_access_token(token)
    assert payload.user_id == "user-123"
    assert payload.username == "testuser"

def test_invalid_token():
    auth = AuthManager(secret="test-secret")
    with pytest.raises(ValueError, match="Invalid token"):
        auth.verify_access_token("invalid-token")

def test_hash_and_verify_password():
    auth = AuthManager(secret="test-secret")
    password = "testpass123"
    hashed = auth.hash_password(password)
    assert hashed != password
    assert auth.verify_password(password, hashed) is True
    assert auth.verify_password("wrongpass", hashed) is False
