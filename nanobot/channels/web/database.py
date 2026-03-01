"""SQLite database for web channel users and sessions."""

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import aiosqlite
import bcrypt
from loguru import logger


class WebDatabase:
    """Async SQLite database for web channel."""

    @staticmethod
    async def create(db_path: str) -> "WebDatabase":
        """Create database and initialize schema."""
        db = WebDatabase(db_path)
        await db.init()
        return db

    def __init__(self, db_path: str):
        """Initialize database with path."""
        self.db_path = Path(db_path).expanduser()
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        """Create database tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)

        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)"
        )

        await self._conn.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()

    # Password utilities
    @staticmethod
    async def hash_password(password: str) -> str:
        """Hash password with bcrypt."""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

    @staticmethod
    async def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode(), password_hash.encode())

    # User operations
    async def create_user(self, username: str, password: str) -> str:
        """Create a new user. Returns user ID (UUID)."""
        user_id = str(uuid.uuid4())
        password_hash = await self.hash_password(password)
        created_at = datetime.utcnow().isoformat()

        try:
            await self._conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user_id, username, password_hash, created_at)
            )
            await self._conn.commit()
            return user_id
        except aiosqlite.IntegrityError:
            raise ValueError(f"Username '{username}' already exists")

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Get user by username."""
        cursor = await self._conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Get user by ID."""
        cursor = await self._conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # Session operations
    async def create_session(self, user_id: str) -> str:
        """Create a new chat session. Returns session ID (UUID)."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        await self._conn.execute(
            "INSERT INTO sessions (id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, user_id, now, now)
        )
        await self._conn.commit()
        return session_id

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session by ID."""
        cursor = await self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_session(self, session_id: str) -> None:
        """Update session timestamp."""
        await self._conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), session_id)
        )
        await self._conn.commit()

    async def list_user_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """List all sessions for a user."""
        cursor = await self._conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # Message operations
    async def add_message(self, session_id: str, role: str, content: str) -> str:
        """Add a message to a session. Returns message ID (UUID)."""
        msg_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        await self._conn.execute(
            "INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (msg_id, session_id, role, content, timestamp)
        )
        await self._conn.commit()
        return msg_id

    async def get_messages(self, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get messages for a session, most recent first."""
        cursor = await self._conn.execute(
            f"SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT {limit}",
            (session_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
