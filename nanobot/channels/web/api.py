"""FastAPI application for web channel."""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from nanobot.bus.queue import MessageBus
from nanobot.channels.web.auth import AuthManager, TokenData
from nanobot.channels.web.database import WebDatabase

from fastapi.responses import StreamingResponse
import json
import asyncio


# In-memory request tracking for SSE streaming
pending_requests: dict[str, dict] = {}


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
    bus: MessageBus,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        db: Database instance
        secret: JWT secret key
        allow_from: Allowed usernames for registration (empty = open)
        bus: Message bus for publishing inbound messages
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

    # Chat models
    class ChatRequest(BaseModel):
        content: str = Field(min_length=1, max_length=10000)
        session_id: str | None = None

    class ChatResponse(BaseModel):
        request_id: str
        session_id: str
        stream_url: str

    class ChatMessage(BaseModel):
        role: str
        content: str
        timestamp: str

    class ChatHistory(BaseModel):
        messages: list[ChatMessage]

    @app.post("/api/chat/completions", response_model=ChatResponse, status_code=status.HTTP_202_ACCEPTED)
    async def create_completion(
        request: ChatRequest,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Annotated[WebDatabase, Depends(get_db)],
    ):
        """Send a message and start AI response stream."""
        import uuid

        # Get or create session
        session_id = request.session_id
        if not session_id:
            session_id = await db.create_session(current_user.user_id)
        else:
            # Verify session belongs to user
            session = await db.get_session(session_id)
            if not session or session["user_id"] != current_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid session"
                )

        # Save user message
        await db.add_message(session_id, "user", request.content)

        # Create request ID
        request_id = str(uuid.uuid4())
        pending_requests[request_id] = {
            "user_id": current_user.user_id,
            "username": current_user.username,
            "session_id": session_id,
            "content": request.content,
        }

        # Publish inbound message to bus
        from nanobot.bus.events import InboundMessage
        inbound_msg = InboundMessage(
            channel="web",
            sender_id=current_user.user_id,
            chat_id=session_id,
            content=request.content,
            media=[],
            metadata={
                "request_id": request_id,
                "username": current_user.username,
            },
            session_key_override=session_id,
        )
        await bus.publish_inbound(inbound_msg)

        return ChatResponse(
            request_id=request_id,
            session_id=session_id,
            stream_url=f"/api/chat/stream?request_id={request_id}"
        )

    @app.get("/api/chat/history", response_model=ChatHistory)
    async def get_history(
        session_id: str,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Annotated[WebDatabase, Depends(get_db)],
        limit: int = 100,
    ):
        """Get chat history for a session."""
        # Verify session belongs to user
        session = await db.get_session(session_id)
        if not session or session["user_id"] != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid session"
            )

        messages = await db.get_messages(session_id, limit=limit)
        return ChatHistory(
            messages=[
                ChatMessage(
                    role=m["role"],
                    content=m["content"],
                    timestamp=m["timestamp"]
                )
                for m in messages
            ]
        )

    # SSE streaming endpoint
    @app.get("/api/chat/stream")
    async def stream_completion(
        request_id: str,
        current_user: Annotated[TokenData, Depends(get_current_user)],
    ):
        """Stream AI response via Server-Sent Events."""

        async def event_stream():
            # Check authorization
            if request_id not in pending_requests:
                yield "event: error\ndata: {\"error\": \"Invalid request_id\"}\n\n"
                return

            req_data = pending_requests[request_id]
            if req_data["user_id"] != current_user.user_id:
                yield "event: error\ndata: {\"error\": \"Unauthorized\"}\n\n"
                return

            # Wait for response
            timeout = 120
            check_interval = 0.1
            elapsed = 0

            while elapsed < timeout:
                if request_id in pending_requests and "response" in pending_requests[request_id]:
                    response = pending_requests[request_id]["response"]

                    # Stream in chunks
                    chunk_size = 10
                    for i in range(0, len(response), chunk_size):
                        chunk = response[i:i+chunk_size]
                        data = json.dumps({"content": chunk, "done": False})
                        yield f"event: message\ndata: {data}\n\n"
                        await asyncio.sleep(0.02)

                    # Done
                    yield "event: done\ndata: {\"done\": true}\n\n"

                    # Save to database
                    session_id = pending_requests[request_id]["session_id"]
                    await app.state.db.add_message(session_id, "assistant", response)

                    # Cleanup
                    del pending_requests[request_id]
                    return

                await asyncio.sleep(check_interval)
                elapsed += check_interval

            # Timeout
            yield "event: error\ndata: {\"error\": \"Request timeout\"}\n\n"
            if request_id in pending_requests:
                del pending_requests[request_id]

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    return app
