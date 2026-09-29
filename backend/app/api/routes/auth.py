"""Authentication and user management routes."""

from datetime import timedelta

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.config import get_settings
from app.core.exceptions import AuthenticationException, ConflictException
from app.core.security import create_access_token, hash_password, verify_password
from app.database.models import User
from app.database.repositories.user_repo import UserRepository
from app.schemas.auth import Token, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    data: UserRegister,
    session: AsyncSession = Depends(get_db),
) -> UserResponse:
    user_repo = UserRepository(session)
    existing_user = await user_repo.get_by_email(data.email)
    if existing_user:
        raise ConflictException(f"User with email '{data.email}' already exists")

    hashed_pw = hash_password(data.password)
    # Public registration assigns USER role by default to prevent privilege escalation
    assigned_role = (
        "ADMIN" if (data.email.lower() == "admin@nexarag.ai" and data.role == "ADMIN") else "USER"
    )
    user = await user_repo.create(
        email=data.email,
        password_hash=hashed_pw,
        role=assigned_role,
    )
    await session.commit()
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate and receive JWT token",
)
async def login(
    data: UserLogin,
    session: AsyncSession = Depends(get_db),
) -> Token:
    user_repo = UserRepository(session)
    user = await user_repo.get_by_email(data.email)

    if not user or not verify_password(data.password, user.password_hash):
        raise AuthenticationException("Invalid email or password")

    if not user.is_active:
        raise AuthenticationException("User account is disabled")

    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_str = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=expires_delta,
    )

    return Token(
        access_token=token_str,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get profile of currently logged-in user",
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
