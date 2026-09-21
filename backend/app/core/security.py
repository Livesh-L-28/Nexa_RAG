"""Security utilities: password hashing, JWT tokens, RBAC, and input sanitization."""

import os
import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import InvalidFileTypeError, UnauthorizedAccessError

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate bcrypt hash for a password."""
    return pwd_context.hash(password)


hash_password = get_password_hash


def create_access_token(
    subject: str | Any | None = None,
    role: str = UserRole.USER.value,
    expires_delta: timedelta | None = None,
    data: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode: dict[str, Any] = {"exp": expire, "iat": datetime.now(timezone.utc)}
    if data:
        to_encode.update(data)
    else:
        to_encode["sub"] = str(subject)
        to_encode["role"] = role

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError as err:
        raise UnauthorizedAccessError("Invalid or expired token.") from err


def sanitize_filename(filename: str) -> str:
    """Sanitize uploaded filenames to prevent path traversal and arbitrary writes.

    Strips directory separators, spaces, and non-alphanumeric characters (except dots and dashes).
    """
    # Normalize Windows backslashes to forward slashes first
    normalized = filename.replace("\\", "/")
    # Keep only the basename
    clean_name = os.path.basename(normalized).strip()
    # Replace whitespace with underscore
    clean_name = re.sub(r"\s+", "_", clean_name)
    # Remove all dangerous characters
    clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "", clean_name)
    # Strip any consecutive dots
    while ".." in clean_name:
        clean_name = clean_name.replace("..", "")

    if not clean_name or clean_name.startswith("."):
        clean_name = f"doc_{clean_name}"

    return clean_name


def validate_file_extension(filename: str) -> str:
    """Validate that the file extension is allowed."""
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise InvalidFileTypeError(
            f"Extension '{ext}' is not supported. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    return ext
