import pytest
from httpx import AsyncClient, ASGITransport
from nanobot.channels.web.api import create_app
from nanobot.channels.web.database import WebDatabase
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
async def db(tmp_path):
    db = await WebDatabase.create(str(tmp_path / "test.db"))
    yield db
    await db.close()

@pytest.fixture
async def app(db):
    return create_app(db=db, secret="test-secret", allow_from=[])

@pytest.mark.asyncio
async def test_register_user(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/register", json={
            "username": "testuser",
            "password": "password123"
        })
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["user"]["username"] == "testuser"

@pytest.mark.asyncio
async def test_register_duplicate_username(app, db):
    await db.create_user("testuser", "password123")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/register", json={
            "username": "testuser",
            "password": "anotherpass"
        })
        assert response.status_code == 409

@pytest.mark.asyncio
async def test_login_success(app, db):
    await db.create_user("testuser", "password123")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "password123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

@pytest.mark.asyncio
async def test_login_invalid_password(app, db):
    await db.create_user("testuser", "password123")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "wrongpass"
        })
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_me_unauthorized(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_me_authorized(app, db):
    user_id = await db.create_user("testuser", "password123")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login first
        login_resp = await client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "password123"
        })
        token = login_resp.json()["access_token"]

        # Get user info
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["username"] == "testuser"

@pytest.mark.asyncio
async def test_chat_completions(app, db):
    user_id = await db.create_user("testuser", "password123")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login
        login_resp = await client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "password123"
        })
        token = login_resp.json()["access_token"]

        # Send message
        response = await client.post(
            "/api/chat/completions",
            json={"content": "Hello"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 202
        data = response.json()
        assert "request_id" in data
        assert "session_id" in data
        assert "stream_url" in data

@pytest.mark.asyncio
async def test_chat_history(app, db):
    user_id = await db.create_user("testuser", "password123")
    session_id = await db.create_session(user_id)
    await db.add_message(session_id, "user", "Hello")
    await db.add_message(session_id, "assistant", "Hi there!")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login
        login_resp = await client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "password123"
        })
        token = login_resp.json()["access_token"]

        # Get history
        response = await client.get(
            f"/api/chat/history?session_id={session_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
