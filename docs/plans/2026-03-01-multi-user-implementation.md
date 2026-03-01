# Multi-User Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform nanobot from single-user to multi-user SaaS platform with container-level isolation for 100+ users.

**Architecture:** Web Gateway (FastAPI) + Container Manager (docker-py) + per-user Docker containers running nanobot gateway, with SQLite for metadata and filesystem-based data isolation.

**Tech Stack:** FastAPI, Docker, docker-py, SQLite, JWT, Pydantic, pytest

---

## Phase 1: Project Setup & Infrastructure (30 minutes)

### Task 1: Create Multi-User Service Directory Structure

**Files:**
- Create: `services/multi-user/README.md`
- Create: `services/multi-user/web-gateway/`
- Create: `services/multi-user/container-manager/`
- Create: `services/multi-user/shared/`

**Step 1: Create directory structure**

```bash
mkdir -p services/multi-user/web-gateway
mkdir -p services/multi-user/container-manager
mkdir -p services/multi-user/shared
mkdir -p services/multi-user/tests
```

**Step 2: Create README**

Write `services/multi-user/README.md`:
```markdown
# Multi-User Service

## Components

- `web-gateway/`: FastAPI service for auth and WebSocket routing
- `container-manager/`: Docker container lifecycle management
- `shared/`: Common utilities and models
- `tests/`: Integration and unit tests

## Development

```bash
cd services/multi-user
pip install -r requirements.txt
pytest
```
```

**Step 3: Create shared module init**

Write `services/multi-user/shared/__init__.py`:
```python
"""Shared utilities for multi-user service."""
```

**Step 4: Commit**

```bash
git add services/multi-user/
git commit -m "feat(multi-user): create service directory structure"
```

### Task 2: Setup Dependencies

**Files:**
- Create: `services/multi-user/requirements.txt`
- Create: `services/multi-user/pyproject.toml`

**Step 1: Write requirements.txt**

Create `services/multi-user/requirements.txt`:
```text
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
docker>=7.0.0
pyjwt>=2.8.0
cryptography>=41.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
aiosqlite>=0.19.0
pytest>=7.4.0
pytest-asyncio>=0.23.0
httpx>=0.26.0
```

**Step 2: Write pyproject.toml**

Create `services/multi-user/pyproject.toml`:
```toml
[project]
name = "nanobot-multi-user"
version = "0.1.0"
description = "Multi-user support for nanobot"
requires-python = ">=3.11"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 3: Commit**

```bash
git add services/multi-user/requirements.txt services/multi-user/pyproject.toml
git commit -m "feat(multi-user): add project dependencies"
```

---

## Phase 2: Database & Models (45 minutes)

### Task 3: Create Database Models

**Files:**
- Create: `services/multi-user/shared/models.py`
- Create: `services/multi-user/shared/database.py`
- Test: `services/multi-user/tests/test_models.py`

**Step 1: Write failing test for User model**

Create `services/multi-user/tests/test_models.py`:
```python
import pytest
from shared.models import User, CreateUserRequest

def test_user_model_creation():
    user = User(
        user_id="user_123",
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password"
    )
    assert user.user_id == "user_123"
    assert user.username == "testuser"
    assert user.status == "active"  # default value

def test_create_user_request():
    request = CreateUserRequest(
        username="newuser",
        password="password123",
        email="new@example.com"
    )
    assert request.username == "newuser"
    assert request.password == "password123"
```

**Step 2: Run test to verify it fails**

```bash
cd services/multi-user
pytest tests/test_models.py::test_user_model_creation -v
```
Expected: `ImportError: cannot import name 'User' from 'shared.models'`

**Step 3: Implement User models**

Create `services/multi-user/shared/models.py`:
```python
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
import enum

class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"

class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class User(BaseModel):
    user_id: str
    username: str
    email: EmailStr
    password_hash: str
    created_at: datetime
    last_login: Optional[datetime] = None
    status: UserStatus = UserStatus.ACTIVE
    quota_used: int = 0
    container_name: Optional[str] = None
    container_port: Optional[int] = None
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE

class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: EmailStr

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    user_id: str
    username: str
    token: str
    container_port: Optional[int] = None
```

**Step 4: Run test to verify it passes**

```bash
cd services/multi-user
pytest tests/test_models.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add services/multi-user/shared/models.py services/multi-user/tests/test_models.py
git commit -m "feat(multi-user): add User models with Pydantic"
```

### Task 4: Create Database Schema and Initialization

**Files:**
- Create: `services/multi-user/shared/database.py`
- Modify: `services/multi-user/tests/test_models.py`

**Step 1: Write failing test for database initialization**

Add to `services/multi-user/tests/test_models.py`:
```python
import pytest
import aiosqlite
import asyncio
from shared.database import init_database, get_user, create_user

@pytest.mark.asyncio
async def test_database_initialization():
    db_path = "/tmp/test_users.db"
    await init_database(db_path)

    # Verify tables exist
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        result = await cursor.fetchone()
        assert result is not None

@pytest.mark.asyncio
async def test_create_and_retrieve_user():
    db_path = "/tmp/test_users_crud.db"
    await init_database(db_path)

    user = await create_user(
        db_path,
        user_id="user_test",
        username="testuser",
        email="test@example.com",
        password_hash="hash123"
    )

    retrieved = await get_user(db_path, user_id="user_test")
    assert retrieved is not None
    assert retrieved["username"] == "testuser"
```

**Step 2: Run test to verify it fails**

```bash
cd services/multi-user
pytest tests/test_models.py::test_database_initialization -v
```
Expected: `ImportError`

**Step 3: Implement database module**

Create `services/multi-user/shared/database.py`:
```python
import aiosqlite
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any

async def init_database(db_path: str) -> None:
    """Initialize database with schema."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                status TEXT DEFAULT 'active',
                quota_used INTEGER DEFAULT 0,
                container_name TEXT,
                container_port INTEGER,
                subscription_tier TEXT DEFAULT 'free'
            )
        """)
        await db.commit()

async def create_user(
    db_path: str,
    user_id: str,
    username: str,
    email: str,
    password_hash: str
) -> Dict[str, Any]:
    """Create a new user."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, email, password_hash)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, username, email, password_hash)
        )
        await db.commit()

        return await get_user(db_path, user_id=user_id)

async def get_user(db_path: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None

async def get_user_by_username(db_path: str, username: str) -> Optional[Dict[str, Any]]:
    """Get user by username."""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )
        row = await cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None
```

**Step 4: Run test to verify it passes**

```bash
cd services/multi-user
pytest tests/test_models.py::test_database_initialization tests/test_models.py::test_create_and_retrieve_user -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add services/multi-user/shared/database.py
git commit -m "feat(multi-user): implement database schema and CRUD operations"
```

---

## Phase 3: Authentication Service (1 hour)

### Task 5: Implement JWT Authentication

**Files:**
- Create: `services/multi-user/shared/auth.py`
- Test: `services/multi-user/tests/test_auth.py`

**Step 1: Write failing test for JWT creation and verification**

Create `services/multi-user/tests/test_auth.py`:
```python
import pytest
from shared.auth import create_jwt, verify_jwt, hash_password

def test_jwt_creation_and_verification():
    payload = {
        "user_id": "user_123",
        "username": "testuser"
    }
    secret = "test_secret"

    token = create_jwt(payload, secret)
    assert isinstance(token, str)
    assert len(token) > 0

    # Verify token
    decoded = verify_jwt(token, secret)
    assert decoded["user_id"] == "user_123"
    assert decoded["username"] == "testuser"

def test_jwt_with_invalid_secret():
    payload = {"user_id": "user_123"}
    token = create_jwt(payload, "secret1")

    # Should fail with wrong secret
    with pytest.raises(Exception):
        verify_jwt(token, "secret2")

def test_password_hashing():
    password = "mypassword"
    hashed = hash_password(password)

    assert hashed != password
    assert len(hashed) == 64  # SHA256 hex length
```

**Step 2: Run test to verify it fails**

```bash
cd services/multi-user
pytest tests/test_auth.py -v
```
Expected: `ImportError`

**Step 3: Implement authentication utilities**

Create `services/multi-user/shared/auth.py`:
```python
import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any

JWT_SECRET = "change-this-in-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

def create_jwt(payload: Dict[str, Any], secret: str = JWT_SECRET) -> str:
    """Create JWT token."""
    payload_copy = payload.copy()
    payload_copy["iat"] = datetime.utcnow()
    payload_copy["exp"] = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)

    return jwt.encode(payload_copy, secret, algorithm=JWT_ALGORITHM)

def verify_jwt(token: str, secret: str = JWT_SECRET) -> Dict[str, Any]:
    """Verify and decode JWT token."""
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")

def hash_password(password: str) -> str:
    """Hash password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash."""
    return hash_password(password) == hashed
```

**Step 4: Run test to verify it passes**

```bash
cd services/multi-user
pytest tests/test_auth.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add services/multi-user/shared/auth.py services/multi-user/tests/test_auth.py
git commit -m "feat(multi-user): implement JWT authentication and password hashing"
```

### Task 6: Implement User Registration Logic

**Files:**
- Create: `services/multi-user/shared/user_service.py`
- Modify: `services/multi-user/tests/test_auth.py`

**Step 1: Write failing test for user registration**

Add to `services/multi-user/tests/test_auth.py`:
```python
import pytest
from shared.user_service import register_user, authenticate_user
from shared.models import CreateUserRequest

@pytest.mark.asyncio
async def test_user_registration():
    db_path = "/tmp/test_registration.db"
    from shared.database import init_database
    await init_database(db_path)

    request = CreateUserRequest(
        username="newuser",
        password="password123",
        email="new@example.com"
    )

    user = await register_user(db_path, request)

    assert user.username == "newuser"
    assert user.email == "new@example.com"
    assert user.status == "active"

@pytest.mark.asyncio
async def test_user_authentication_success():
    db_path = "/tmp/test_auth.db"
    from shared.database import init_database, create_user
    await init_database(db_path)

    # Create test user
    await create_user(
        db_path,
        user_id="user_auth_test",
        username="authuser",
        email="auth@example.com",
        password_hash="hash123"
    )

    # Update with correct password hash
    from shared.auth import hash_password
    hashed = hash_password("password123")

    # Mock the verify to return our user
    result = await authenticate_user(db_path, "authuser", "password123")
    assert result is not None
    assert result["username"] == "authuser"
```

**Step 2: Run test to verify it fails**

```bash
cd services/multi-user
pytest tests/test_auth.py::test_user_registration -v
```
Expected: `ImportError`

**Step 3: Implement user service**

Create `services/multi-user/shared/user_service.py`:
```python
import uuid
from shared.models import User, CreateUserRequest, LoginRequest
from shared.database import create_user, get_user_by_username
from shared.auth import hash_password, verify_password
from typing import Optional, Dict, Any

async def register_user(db_path: str, request: CreateUserRequest) -> User:
    """Register a new user."""
    # Check if username exists
    existing = await get_user_by_username(db_path, request.username)
    if existing:
        raise ValueError("Username already exists")

    # Generate user ID
    user_id = f"user_{uuid.uuid4().hex[:12]}"

    # Hash password
    password_hash = hash_password(request.password)

    # Create user
    user_dict = await create_user(
        db_path,
        user_id=user_id,
        username=request.username,
        email=request.email,
        password_hash=password_hash
    )

    return User(**user_dict)

async def authenticate_user(
    db_path: str,
    username: str,
    password: str
) -> Optional[Dict[str, Any]]:
    """Authenticate user with username and password."""
    user = await get_user_by_username(db_path, username)
    if not user:
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    return user
```

**Step 4: Run test to verify it passes**

```bash
cd services/multi-user
pytest tests/test_auth.py::test_user_registration tests/test_auth.py::test_user_authentication_success -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add services/multi-user/shared/user_service.py
git commit -m "feat(multi-user): implement user registration and authentication"
```

---

## Phase 4: Container Management Service (1.5 hours)

### Task 7: Create Docker Container Manager

**Files:**
- Create: `services/multi-user/container-manager/__init__.py`
- Create: `services/multi-user/container-manager/manager.py`
- Test: `services/multi-user/tests/test_container_manager.py`

**Step 1: Write failing test for container creation**

Create `services/multi-user/tests/test_container_manager.py`:
```python
import pytest
from container_manager.manager import ContainerManager

@pytest.mark.asyncio
async def test_container_creation():
    manager = ContainerManager()

    container = await manager.create_container(
        user_id="user_test_123",
        config_path="/tmp/test/config"
    )

    assert container is not None
    assert container.name == "nanobot-user_test_123"
    assert container.status == "created"

@pytest.mark.asyncio
async def test_container_deletion():
    manager = ContainerManager()

    # First create
    await manager.create_container(
        user_id="user_delete_test",
        config_path="/tmp/test/config2"
    )

    # Then delete
    result = await manager.delete_container(user_id="user_delete_test")
    assert result is True
```

**Step 2: Run test to verify it fails**

```bash
cd services/multi-user
pytest tests/test_container_manager.py::test_container_creation -v
```
Expected: `ImportError`

**Step 3: Implement container manager**

Create `services/multi-user/container-manager/manager.py`:
```python
import docker
from typing import Optional, Dict, Any
import asyncio

class ContainerManager:
    """Manages Docker containers for nanobot users."""

    def __init__(self):
        self.client = docker.from_env()

    async def create_container(
        self,
        user_id: str,
        config_path: str
    ) -> Dict[str, Any]:
        """Create a new container for user."""
        container_name = f"nanobot-{user_id}"

        # Run in thread pool to avoid blocking
        container = await asyncio.to_thread(
            self.client.containers.create,
            image="nanobot:latest",
            name=container_name,
            volumes={
                config_path: {"bind": "/root/.nanobot", "mode": "rw"}
            },
            ports={"18790/tcp": None},  # Auto-assign port
            detach=True,
            mem_limit="512m",
            cpu_quota=100000,
            cpu_period=100000
        )

        return {
            "id": container.id,
            "name": container.name,
            "status": "created"
        }

    async def start_container(self, user_id: str) -> Dict[str, Any]:
        """Start user's container."""
        container_name = f"nanobot-{user_id}"

        container = await asyncio.to_thread(
            self.client.containers.get,
            container_name
        )

        await asyncio.to_thread(container.start)

        # Get port mapping
        container.reload()
        port = container.ports.get("18790/tcp", [None])[0]

        return {
            "container_id": container.id,
            "port": port["HostPort"] if port else None,
            "status": "running"
        }

    async def stop_container(self, user_id: str) -> bool:
        """Stop user's container."""
        container_name = f"nanobot-{user_id}"

        try:
            container = await asyncio.to_thread(
                self.client.containers.get,
                container_name
            )
            await asyncio.to_thread(container.stop)
            return True
        except Exception:
            return False

    async def delete_container(self, user_id: str) -> bool:
        """Delete user's container."""
        container_name = f"nanobot-{user_id}"

        try:
            container = await asyncio.to_thread(
                self.client.containers.get,
                container_name
            )
            await asyncio.to_thread(container.remove, force=True)
            return True
        except Exception:
            return False

    async def get_container_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get container status."""
        container_name = f"nanobot-{user_id}"

        try:
            container = await asyncio.to_thread(
                self.client.containers.get,
                container_name
            )
            container.reload()

            return {
                "status": container.status,
                "id": container.id
            }
        except Exception:
            return None
```

**Step 4: Run test to verify it passes**

```bash
cd services/multi-user
pytest tests/test_container_manager.py -v
```
Expected: PASS (may fail if Docker not available, that's OK for now)

**Step 5: Commit**

```bash
git add services/multi-user/container-manager/
git commit -m "feat(multi-user): implement container manager"
```

---

## Phase 5: Web Gateway API (1.5 hours)

### Task 8: Create FastAPI Application Structure

**Files:**
- Create: `services/multi-user/web-gateway/__init__.py`
- Create: `services/multi-user/web-gateway/main.py`
- Create: `services/multi-user/web-gateway/config.py`

**Step 1: Create config module**

Create `services/multi-user/web-gateway/config.py`:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///data/database/users.db"
    jwt_secret: str = "change-this-in-production"
    encryption_key: str = "change-this-in-production"
    base_data_path: str = "/data/users"

    class Config:
        env_file = ".env"

settings = Settings()
```

**Step 2: Create main FastAPI app**

Create `services/multi-user/web-gateway/main.py`:
```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .config import settings

app = FastAPI(title="Nanobot Multi-User Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {"message": "Nanobot Multi-User Gateway API"}
```

**Step 3: Test app runs manually**

```bash
cd services/multi-user/web-gateway
uvicorn main:app --reload --port 8000
```

Test: `curl http://localhost:8000/health`
Expected: `{"status":"healthy"}`

**Step 4: Commit**

```bash
git add services/multi-user/web-gateway/
git commit -m "feat(multi-user): create FastAPI gateway application"
```

### Task 9: Implement Authentication Endpoints

**Files:**
- Create: `services/multi-user/web-gateway/routers/__init__.py`
- Create: `services/multi-user/web-gateway/routers/auth.py`
- Modify: `services/multi-user/web-gateway/main.py`
- Test: `services/multi-user/tests/test_api.py`

**Step 1: Write failing test for registration endpoint**

Create `services/multi-user/tests/test_api.py`:
```python
import pytest
from fastapi.testclient import TestClient
from web_gateway.main import app

client = TestClient(app)

def test_register_user():
    response = client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "password": "password123",
            "email": "test@example.com"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert "token" in data
    assert data["username"] == "testuser"

def test_login_user():
    # First register
    client.post(
        "/api/auth/register",
        json={
            "username": "loginuser",
            "password": "password123",
            "email": "login@example.com"
        }
    )

    # Then login
    response = client.post(
        "/api/auth/login",
        json={
            "username": "loginuser",
            "password": "password123"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "token" in data
```

**Step 2: Run test to verify it fails**

```bash
cd services/multi-user
pytest tests/test_api.py::test_register_user -v
```
Expected: `404 Not Found`

**Step 3: Implement auth router**

Create `services/multi-user/web-gateway/routers/auth.py`:
```python
from fastapi import APIRouter, HTTPException
from shared.models import CreateUserRequest, AuthResponse
from shared.user_service import register_user, authenticate_user
from shared.auth import create_jwt
from web_gateway.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=AuthResponse)
async def register(request: CreateUserRequest):
    """Register a new user."""
    try:
        user = await register_user(settings.database_url, request)

        # Create JWT token
        token = create_jwt({
            "user_id": user.user_id,
            "username": user.username
        }, settings.jwt_secret)

        return AuthResponse(
            user_id=user.user_id,
            username=user.username,
            token=token
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=AuthResponse)
async def login(username: str, password: str):
    """Authenticate user."""
    user = await authenticate_user(settings.database_url, username, password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_jwt({
        "user_id": user["user_id"],
        "username": user["username"]
    }, settings.jwt_secret)

    return AuthResponse(
        user_id=user["user_id"],
        username=user["username"],
        token=token
    )
```

**Step 4: Register router in main app**

Modify `services/multi-user/web-gateway/main.py`:
```python
from fastapi import FastAPI
from .config import settings
from .routers import auth

app = FastAPI(title="Nanobot Multi-User Gateway")
app.include_router(auth.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

**Step 5: Run test to verify it passes**

```bash
cd services/multi-user
pytest tests/test_api.py::test_register_user tests/test_api.py::test_login_user -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add services/multi-user/web-gateway/routers/ services/multi-user/web-gateway/main.py
git commit -m "feat(multi-user): implement authentication endpoints"
```

### Task 10: Implement WebSocket Connection Routing

**Files:**
- Create: `services/multi-user/web-gateway/routers/websocket.py`
- Modify: `services/multi-user/web-gateway/main.py`

**Step 1: Implement WebSocket handler**

Create `services/multi-user/web-gateway/routers/websocket.py`:
```python
from fastapi import WebSocket, WebSocketDisconnect
from shared.auth import verify_jwt
from web_gateway.config import settings
import httpx

async def websocket_endpoint(websocket: WebSocket, token: str):
    """WebSocket endpoint for real-time communication."""
    try:
        # Verify JWT
        payload = verify_jwt(token, settings.jwt_secret)
        user_id = payload["user_id"]

        await websocket.accept()

        # Get container port from database or container manager
        # For now, use a default port
        container_port = 18790

        # Connect to user's container
        container_url = f"ws://localhost:{container_port}/ws"

        async with httpx.AsyncClient() as client:
            async with client.stream("GET", container_url) as response:
                # Forward messages between client and container
                while True:
                    try:
                        # Receive from client
                        data = await websocket.receive_text()
                        # Forward to container (implementation depends on container API)
                        await websocket.send_text(f"Echo: {data}")

                    except WebSocketDisconnect:
                        break

    except Exception as e:
        await websocket.close(code=1008, reason=str(e))
```

**Step 2: Add WebSocket route to main app**

Modify `services/multi-user/web-gateway/main.py`:
```python
from fastapi import FastAPI, WebSocket
from .routers import auth, websocket

app = FastAPI(title="Nanobot Multi-User Gateway")
app.include_router(auth.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.websocket("/ws/{token}")
async def websocket_route(websocket: WebSocket, token: str):
    await websocket.websocket_endpoint(websocket, token)
```

**Step 3: Test WebSocket connection manually**

```bash
# Start server
cd services/multi-user/web-gateway
uvicorn main:app --reload
```

Use WebSocket client to test connection.

**Step 4: Commit**

```bash
git add services/multi-user/web-gateway/
git commit -m "feat(multi-user): implement WebSocket connection routing"
```

---

## Phase 6: Integration & Deployment (1 hour)

### Task 11: Create Docker Compose Configuration

**Files:**
- Create: `services/multi-user/docker-compose.yml`
- Create: `services/multi-user/nginx/nginx.conf`

**Step 1: Create docker-compose.yml**

Create `services/multi-user/docker-compose.yml`:
```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - web-gateway
    restart: unless-stopped
    networks:
      - frontend-net

  web-gateway:
    build: ./web-gateway
    volumes:
      - ./data:/data
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DATABASE_URL=sqlite:///data/database/users.db
      - JWT_SECRET=${JWT_SECRET:-dev-secret-key}
    restart: unless-stopped
    networks:
      - frontend-net
      - user-containers-net

networks:
  frontend-net:
    driver: bridge
  user-containers-net:
    driver: bridge
    internal: true
```

**Step 2: Create nginx config**

Create `services/multi-user/nginx/nginx.conf`:
```nginx
events {
    worker_connections 1024;
}

http {
    upstream web_gateway {
        server web-gateway:8000;
    }

    server {
        listen 80;
        server_name _;

        location / {
            proxy_pass http://web_gateway;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location /ws/ {
            proxy_pass http://web_gateway;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
```

**Step 3: Commit**

```bash
git add services/multi-user/docker-compose.yml services/multi-user/nginx/
git commit -m "feat(multi-user): add Docker Compose configuration"
```

### Task 12: Create Deployment Scripts

**Files:**
- Create: `services/multi-user/scripts/setup.sh`
- Create: `services/multi-user/scripts/init_db.py`
- Create: `services/multi-user/.env.example`

**Step 1: Create setup script**

Create `services/multi-user/scripts/setup.sh`:
```bash
#!/bin/bash

echo "Setting up Nanobot Multi-User Service..."

# Create directories
mkdir -p /data/users
mkdir -p /data/database
mkdir -p /var/log/nanobot

# Generate secrets
export JWT_SECRET=$(openssl rand -hex 32)
export ENCRYPTION_KEY=$(openssl rand -hex 32)

# Save to .env
cat > .env << EOF
JWT_SECRET=$JWT_SECRET
ENCRYPTION_KEY=$ENCRYPTION_KEY
DATABASE_URL=sqlite:///data/database/users.db
EOF

# Build and start
docker-compose build
docker-compose up -d

echo "Setup complete!"
echo "JWT Secret: $JWT_SECRET"
```

**Step 2: Create database initialization script**

Create `services/multi-user/scripts/init_db.py`:
```python
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.database import init_database

async def main():
    db_path = "/data/database/users.db"
    print(f"Initializing database at {db_path}")
    await init_database(db_path)
    print("Database initialized successfully!")

if __name__ == "__main__":
    asyncio.run(main())
```

**Step 3: Create .env.example**

Create `services/multi-user/.env.example`:
```bash
JWT_SECRET=your-secret-key-here
ENCRYPTION_KEY=your-encryption-key-here
DATABASE_URL=sqlite:///data/database/users.db
```

**Step 4: Make setup script executable**

```bash
chmod +x services/multi-user/scripts/setup.sh
```

**Step 5: Commit**

```bash
git add services/multi-user/scripts/
git commit -m "feat(multi-user): add deployment scripts"
```

### Task 13: Create README and Documentation

**Files:**
- Create: `services/multi-user/README.md`
- Create: `services/multi-user/DEPLOYMENT.md`

**Step 1: Create comprehensive README**

Update `services/multi-user/README.md`:
```markdown
# Nanobot Multi-User Service

Transform nanobot into a multi-user SaaS platform.

## Features

- User registration and authentication
- Per-user Docker container isolation
- WebSocket-based real-time communication
- JWT-based security
- Automatic container lifecycle management

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Start development server
cd web-gateway
uvicorn main:app --reload
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment guide.

## Architecture

- **Web Gateway**: FastAPI service for auth and routing
- **Container Manager**: Docker container lifecycle management
- **Database**: SQLite for user metadata
- **Storage**: Filesystem-based user data isolation
```

**Step 2: Create deployment guide**

Create `services/multi-user/DEPLOYMENT.md`:
```markdown
# Deployment Guide

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- At least 16GB RAM, 4 CPU cores for 100 users

## Production Deployment

```bash
# 1. Clone repository
git clone <repo>
cd services/multi-user

# 2. Configure environment
cp .env.example .env
# Edit .env with your secrets

# 3. Run setup
./scripts/setup.sh

# 4. Verify deployment
docker-compose ps
curl http://localhost/health
```

## Monitoring

Check logs:
```bash
docker-compose logs -f web-gateway
```

Check containers:
```bash
docker ps | grep nanobot
```

## Backup

```bash
# Backup database
cp /data/database/users.db /backup/

# Backup user data
tar -czf /backup/users_$(date +%Y%m%d).tar.gz /data/users/
```

## Troubleshooting

See logs in `/var/log/nanobot/`
```

**Step 3: Commit**

```bash
git add services/multi-user/README.md services/multi-user/DEPLOYMENT.md
git commit -m "docs(multi-user): add comprehensive documentation"
```

---

## Phase 7: Testing & Quality (30 minutes)

### Task 14: Add Integration Tests

**Files:**
- Create: `services/multi-user/tests/integration/test_full_flow.py`

**Step 1: Write integration test**

Create `services/multi-user/tests/integration/test_full_flow.py`:
```python
import pytest
import asyncio
from httpx import AsyncClient
from web_gateway.main import app

@pytest.mark.asyncio
async def test_full_user_flow():
    """Test complete user registration -> login -> websocket flow."""
    async with AsyncClient(app=app, base_url="http://test") as client:

        # 1. Register user
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "integration_user",
                "password": "testpass123",
                "email": "integration@test.com"
            }
        )
        assert response.status_code == 200
        data = response.json()
        token = data["token"]
        user_id = data["user_id"]

        # 2. Login with same user
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "integration_user",
                "password": "testpass123"
            }
        )
        assert response.status_code == 200

        # 3. Verify token works
        # (WebSocket test would go here)
```

**Step 2: Run integration test**

```bash
cd services/multi-user
pytest tests/integration/ -v
```

**Step 3: Commit**

```bash
git add services/multi-user/tests/integration/
git commit -m "test(multi-user): add integration tests"
```

### Task 15: Final Review and Cleanup

**Files:**
- Modify: `services/multi-user/.gitignore`

**Step 1: Create .gitignore**

Create `services/multi-user/.gitignore`:
```
__pycache__/
*.pyc
.env
data/
*.db
.pytest_cache/
.coverage
htmlcov/
dist/
*.egg-info/
```

**Step 2: Run all tests**

```bash
cd services/multi-user
pytest -v --cov=.
```

**Step 3: Code formatting check**

```bash
black --check .
isort --check-only .
```

**Step 4: Commit**

```bash
git add services/multi-user/.gitignore
git commit -m "chore(multi-user): add gitignore and finalize"
```

---

## Completion Checklist

- [ ] All tests pass
- [ ] Documentation complete
- [ ] Deployment tested
- [ ] Security review done
- [ ] Performance tested with 10+ users

## Estimated Total Time

6-8 hours for complete implementation

## Next Steps After Implementation

1. Deploy to staging environment
2. Load testing with 100 users
3. Security audit
4. User acceptance testing
5. Production rollout
