"""Pydantic schemas for authentication and user accounts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password with minimum 8 characters")
    role: str | None = Field(default="USER", pattern="^(USER|ADMIN)$")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str
    role: str
    exp: int


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
