from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import EmailStr
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts import enums
from src.accounts.helpers import (
    _is_expired,
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from src.accounts.models import (
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserGroup,
    UserProfile,
)
from src.accounts.schemas import (
    AccessResponse,
    ActivateSchema,
    ActivationResponse,
    ChangePasswordSchema,
    ForgotPasswordSchema,
    LoginSchema,
    LogoutSchema,
    ProfileUpdateSchema,
    RefreshSchema,
    RegisterSchema,
    ResendActivationSchema,
    ResetPasswordSchema,
    ResetResponse,
    Token,
    UserResponse,
)
from src.config import settings
from src.database import get_db
from src.general_schemas import StatusResponse

router = APIRouter()


@router.post(
    "/register",
    response_model=ActivationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account. Returns an activation token "
    "that must be submitted to the activation endpoint. "
    "Password must be 8-128 characters and include uppercase, lowercase, digit, "
    "and special character.",
    responses={
        400: {"description": "User with this email already exists"},
    },
)
async def register(
    data: RegisterSchema, db: AsyncSession = Depends(get_db)
) -> ActivationResponse:
    q = await db.execute(select(User).where(User.email == data.email))  # type: ignore
    if q.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists"
        )

    # ensure user group exists
    qg = await db.execute(
        select(UserGroup).where(UserGroup.name == enums.UserGroupEnum.USER.value)
    )  # type: ignore
    group = qg.scalars().first()
    if not group:
        group = UserGroup(name=enums.UserGroupEnum.USER.value)
        db.add(group)
        await db.commit()
        await db.refresh(group)

    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        is_active=False,
        group_id=group.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token_str = uuid4().hex
    expires = datetime.now(UTC) + timedelta(
        hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS
    )
    activation = ActivationToken(user_id=user.id, token=token_str, expires_at=expires)
    db.add(activation)
    await db.commit()

    # In production, send email. Here return token for tests/dev.
    return ActivationResponse(activation_token=token_str)


@router.post(
    "/activation",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate user account",
    description="Activate a user account using the token received during registration.",
    responses={
        400: {"description": "Invalid or expired activation token"},
    },
)
async def activate(
    data: ActivateSchema, db: AsyncSession = Depends(get_db)
) -> StatusResponse:
    q = await db.execute(
        select(ActivationToken).where(ActivationToken.token == data.token)
    )  # type: ignore
    at = cast(ActivationToken | None, q.scalars().first())
    if not at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )
    expires = cast(datetime | None, at.expires_at)
    if _is_expired(expires):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )
    q = await db.execute(select(User).where(User.id == at.user_id))  # type: ignore
    user = cast(User | None, q.scalars().first())
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User not found"
        )
    user.is_active = True
    await db.delete(at)
    await db.commit()
    return StatusResponse(status="activated")


@router.post(
    "/activation/resend",
    response_model=ActivationResponse,
    summary="Resend activation token",
    description="Generate a new activation token for an inactive account. "
    "The previous token is invalidated.",
    responses={
        400: {"description": "User is already active"},
        404: {"description": "User not found"},
    },
)
async def resend_activation(
    data: ResendActivationSchema, db: AsyncSession = Depends(get_db)
) -> ActivationResponse:
    q = await db.execute(select(User).where(User.email == data.email))  # type: ignore
    user = q.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User already active"
        )
    # remove old token
    await db.execute(delete(ActivationToken).where(ActivationToken.user_id == user.id))  # type: ignore
    token_str = uuid4().hex
    expires = datetime.now(UTC) + timedelta(
        hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS
    )
    activation = ActivationToken(
        user_id=cast(int, user.id), token=token_str, expires_at=expires
    )
    db.add(activation)
    await db.commit()
    return ActivationResponse(activation_token=token_str)


@router.post(
    "/login",
    response_model=Token,
    summary="Log in",
    description="Authenticate with email and password. Returns a JWT access token "
    "and an opaque refresh token. The account must be activated first.",
    responses={
        401: {"description": "Invalid credentials"},
        403: {"description": "Account is not activated"},
    },
)
async def login(data: LoginSchema, db: AsyncSession = Depends(get_db)) -> Token:
    q = await db.execute(select(User).where(User.email == data.username))  # type: ignore
    user = q.scalars().first()
    if not user or not verify_password(data.password, cast(str, user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )

    access_token = create_access_token(cast(int, user.id))
    refresh_token_str = uuid4().hex
    expires = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(
        user_id=cast(int, user.id), token=refresh_token_str, expires_at=expires
    )
    db.add(rt)
    await db.commit()

    return Token(access_token=access_token, refresh_token=refresh_token_str)


@router.post(
    "/logout",
    response_model=StatusResponse,
    summary="Log out",
    description="Invalidate the provided refresh token. Requires a valid access token.",
)
async def logout(
    data: LogoutSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatusResponse:
    await db.execute(
        delete(RefreshToken).where(
            RefreshToken.token == data.refresh_token,
            RefreshToken.user_id == current_user.id,
        )
    )  # type: ignore
    await db.commit()
    return StatusResponse(status="logged_out")


@router.post(
    "/refresh",
    response_model=AccessResponse,
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new JWT access token.",
    responses={
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh(
    data: RefreshSchema, db: AsyncSession = Depends(get_db)
) -> AccessResponse:
    q = await db.execute(
        select(RefreshToken).where(RefreshToken.token == data.refresh_token)
    )  # type: ignore
    rt = q.scalars().first()
    if not rt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    expires = cast(datetime | None, rt.expires_at)
    if _is_expired(expires):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    access_token = create_access_token(cast(int, rt.user_id))
    return AccessResponse(access_token=access_token)


@router.patch(
    "/change-password",
    response_model=StatusResponse,
    summary="Change password",
    description="Change the current user's password. Requires the old password "
    "for verification. New password must meet complexity requirements.",
    responses={
        400: {"description": "Old password does not match"},
    },
)
async def change_password(
    data: ChangePasswordSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatusResponse:
    if not verify_password(data.old_password, cast(str, current_user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Old password mismatch"
        )
    current_user.hashed_password = get_password_hash(data.new_password)
    await db.commit()
    return StatusResponse(status="password_changed")


@router.post(
    "/forgot-password",
    response_model=ResetResponse,
    summary="Request password reset",
    description="Request a password-reset token. If the email exists, a token is returned "
    "(in production it would be sent via email). Returns an empty token if the user "
    "is not found to avoid revealing account existence.",
)
async def forgot_password(
    data: ForgotPasswordSchema, db: AsyncSession = Depends(get_db)
) -> ResetResponse:
    q = await db.execute(select(User).where(User.email == data.email))  # type: ignore
    user = q.scalars().first()
    if not user:
        # do not reveal user existence (in real project write
        # "sent email with instructions if user exists" and send email if found)
        return ResetResponse(reset_token="")
    await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )  # type: ignore
    token_str = uuid4().hex
    expires = datetime.now(UTC) + timedelta(
        hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
    )
    prt = PasswordResetToken(
        user_id=cast(int, user.id), token=token_str, expires_at=expires
    )
    db.add(prt)
    await db.commit()
    return ResetResponse(reset_token=token_str)


@router.post(
    "/reset-password",
    response_model=StatusResponse,
    summary="Reset password",
    description="Set a new password using the reset token from the forgot-password endpoint.",
    responses={
        400: {"description": "Invalid / expired token or user not found"},
    },
)
async def reset_password(
    data: ResetPasswordSchema, db: AsyncSession = Depends(get_db)
) -> StatusResponse:
    q = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == data.token)
    )  # type: ignore
    prt = cast(PasswordResetToken | None, q.scalars().first())
    if not prt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )
    expires = cast(datetime | None, prt.expires_at)
    if _is_expired(expires):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )
    q = await db.execute(select(User).where(User.id == prt.user_id))  # type: ignore
    found_user = cast(User | None, q.scalars().first())
    if not found_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User not found"
        )
    found_user.hashed_password = get_password_hash(data.new_password)
    await db.delete(prt)
    await db.commit()
    return StatusResponse(status="password_reset")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Return the authenticated user's ID, email, activation status, and role.",
)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    # convert stored group name (string) to UserGroupEnum
    # for Pydantic validation/serialization
    group_enum = None
    group_name = getattr(current_user.group, "name", None)
    if group_name:
        try:
            group_enum = enums.UserGroupEnum(group_name)
        except Exception:
            group_enum = None
    return UserResponse(
        id=cast(int, current_user.id),
        email=cast(EmailStr, current_user.email),
        is_active=cast(bool, current_user.is_active),
        group=group_enum,
    )


@router.patch(
    "/me/profile",
    response_model=StatusResponse,
    summary="Update profile",
    description="Partially update the current user's profile. Only fields included "
    "in the request body are changed; omitted fields are left untouched. "
    "Send a field with `null` to clear it.",
)
async def update_profile(
    data: ProfileUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatusResponse:
    q = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )  # type: ignore
    profile = q.scalars().first()
    if not profile:
        profile = UserProfile(user_id=cast(int, current_user.id))
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    # apply only the fields the client actually sent
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "gender":
            # store string value in DB (SQLite)
            profile.gender = value.value if value is not None else None
        elif field == "date_of_birth":
            profile.date_of_birth = cast(Any, value)
        else:
            setattr(profile, field, value)

    await db.commit()
    return StatusResponse(status="profile_updated")


# Admin endpoints (user management) were moved to src.admin.routers
