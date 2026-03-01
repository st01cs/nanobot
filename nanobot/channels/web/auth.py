"""Authentication utilities for web channel."""

import bcrypt
from datetime import datetime, timedelta
from typing import NamedTuple

from jose import JWTError, jwt


class TokenData(NamedTuple):
    """JWT token payload."""

    user_id: str
    username: str


class AuthManager:
    """Manages JWT tokens and password hashing."""

    def __init__(self, secret: str, expire_days: int = 7):
        """Initialize auth manager.

        Args:
            secret: Secret key for JWT signing
            expire_days: Token expiration time in days
        """
        self.secret_key = secret
        self.algorithm = "HS256"
        self.expire_days = expire_days

    def create_access_token(self, user_id: str, username: str) -> str:
        """Create JWT access token.

        Args:
            user_id: User's unique ID
            username: User's username

        Returns:
            JWT token string
        """
        expire = datetime.utcnow() + timedelta(days=self.expire_days)
        payload = {
            "user_id": user_id,
            "username": username,
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def verify_access_token(self, token: str) -> TokenData:
        """Verify and decode JWT token.

        Args:
            token: JWT token string

        Returns:
            TokenData with user_id and username

        Raises:
            ValueError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id = payload.get("user_id")
            username = payload.get("username")

            if user_id is None or username is None:
                raise ValueError("Invalid token payload")

            return TokenData(user_id=user_id, username=username)

        except JWTError as e:
            raise ValueError(f"Invalid token: {e}")

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash.

        Args:
            password: Plain text password
            password_hash: Hashed password

        Returns:
            True if password matches
        """
        return bcrypt.checkpw(password.encode(), password_hash.encode())
