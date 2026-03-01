import pytest
import asyncio
from pathlib import Path
from nanobot.channels.web.database import WebDatabase

@pytest.fixture
async def db_path(tmp_path):
    return tmp_path / "test.db"

@pytest.mark.asyncio
async def test_create_user(db_path):
    db = await WebDatabase.create(str(db_path))
    user_id = await db.create_user("testuser", "password123")
    assert user_id is not None
    assert len(user_id) == 36  # UUID format

@pytest.mark.asyncio
async def test_duplicate_username(db_path):
    db = await WebDatabase.create(str(db_path))
    await db.create_user("testuser", "password123")
    with pytest.raises(ValueError, match="already exists"):
        await db.create_user("testuser", "anotherpass")

@pytest.mark.asyncio
async def test_verify_password(db_path):
    db = await WebDatabase.create(str(db_path))
    user_id = await db.create_user("testuser", "password123")
    user = await db.get_user_by_username("testuser")
    assert user is not None
    assert user["username"] == "testuser"
    assert await db.verify_password("password123", user["password_hash"]) is True
    assert await db.verify_password("wrongpass", user["password_hash"]) is False

@pytest.mark.asyncio
async def test_get_user_by_id(db_path):
    db = await WebDatabase.create(str(db_path))
    user_id = await db.create_user("testuser", "password123")
    user = await db.get_user_by_id(user_id)
    assert user["username"] == "testuser"

@pytest.mark.asyncio
async def test_session_crud(db_path):
    db = await WebDatabase.create(str(db_path))
    user_id = await db.create_user("testuser", "password123")

    # Create session
    session_id = await db.create_session(user_id)
    assert session_id is not None

    # Get session
    session = await db.get_session(session_id)
    assert session["user_id"] == user_id

    # Update session
    await db.update_session(session_id)
    session = await db.get_session(session_id)
    assert session["updated_at"] != session["created_at"]

@pytest.mark.asyncio
async def test_message_crud(db_path):
    db = await WebDatabase.create(str(db_path))
    user_id = await db.create_user("testuser", "password123")
    session_id = await db.create_session(user_id)

    # Add message
    msg_id = await db.add_message(session_id, "user", "Hello")
    assert msg_id is not None

    # Get messages
    messages = await db.get_messages(session_id, limit=10)
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello"
    assert messages[0]["role"] == "user"
