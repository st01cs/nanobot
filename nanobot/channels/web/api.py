"""FastAPI application for web channel."""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from nanobot.channels.web.auth import AuthManager, TokenData
from nanobot.channels.web.database import WebDatabase


# Request/Response models
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=6, max_length=100)


class UserLogin(BaseModel):
    username: str
    password: str


class User(BaseModel):
    id: str
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User


# Dependencies
security = HTTPBearer(auto_error=False)


def create_app(
    db: WebDatabase,
    secret: str,
    allow_from: list[str],
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        db: Database instance
        secret: JWT secret key
        allow_from: Allowed usernames for registration (empty = open)
        cors_origins: CORS allowed origins

    Returns:
        FastAPI application instance
    """
    app = FastAPI(title="nanobot Web Channel")

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["http://localhost:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    auth_manager = AuthManager(secret=secret)

    # Dependency: get current user from token
    async def get_current_user(
        credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
    ) -> TokenData:
        """Verify JWT and return current user."""
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        try:
            token_data = auth_manager.verify_access_token(credentials.credentials)
            return token_data
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
            )

    # Dependency: get database
    async def get_db() -> WebDatabase:
        return db

    # Auth endpoints
    @app.post("/api/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
    async def register(user_data: UserCreate, db: Annotated[WebDatabase, Depends(get_db)]):
        """Register a new user."""
        # Check if registration is restricted
        if allow_from and user_data.username not in allow_from:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration is restricted"
            )

        # Check if username exists
        existing = await db.get_user_by_username(user_data.username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists"
            )

        # Create user
        user_id = await db.create_user(user_data.username, user_data.password)
        token = auth_manager.create_access_token(user_id, user_data.username)

        return TokenResponse(
            access_token=token,
            user=User(id=user_id, username=user_data.username)
        )

    @app.post("/api/auth/login", response_model=TokenResponse)
    async def login(user_data: UserLogin, db: Annotated[WebDatabase, Depends(get_db)]):
        """Login and receive JWT token."""
        user = await db.get_user_by_username(user_data.username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        # Verify password
        if not auth_manager.verify_password(user_data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        token = auth_manager.create_access_token(user["id"], user["username"])

        return TokenResponse(
            access_token=token,
            user=User(id=user["id"], username=user["username"])
        )

    @app.get("/api/auth/me", response_model=User)
    async def get_me(current_user: Annotated[TokenData, Depends(get_current_user)]):
        """Get current user info."""
        return User(id=current_user.user_id, username=current_user.username)

    return app
