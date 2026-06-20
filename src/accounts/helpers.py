from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.accounts import enums
from src.accounts.models import User
from src.config import settings
from src.database import get_db

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/accounts/login")

logger = logging.getLogger(__name__)


def _truncate_password(pw: str) -> str:
    """No-op truncation.

    The project uses pbkdf2_sha256 (no 72-byte bcrypt limitation), so do not
    truncate passwords here. Keep function for compatibility in case the
    hashing scheme changes in future.
    """
    return pw


def verify_password(plain: str, hashed: str):
    return pwd_context.verify(_truncate_password(plain), hashed)


def get_password_hash(password: str):
    return pwd_context.hash(_truncate_password(password))


def _ensure_aware(dt: datetime) -> datetime:
    """Return datetime as UTC-aware. If dt is naive, assume UTC.

    Expects dt is not None.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _is_expired(dt: datetime | None) -> bool:
    """Return True if dt is None or dt is before now (UTC).

    SQLite stores timestamps without tzinfo; normalize both sides to naive UTC
    datetimes for comparison to avoid offset-naive vs offset-aware errors.
    """
    if dt is None:
        return True

    # convert to aware UTC and compare timestamps
    try:
        left_aware = _ensure_aware(dt)  # type: ignore[arg-type]
    except Exception:
        return True
    # left_aware now guaranteed to be datetime
    right_ts = datetime.now(UTC).timestamp()
    return left_aware.timestamp() < right_ts


def create_access_token(subject: int, expires_delta: timedelta | None = None):
    # use timezone-aware UTC for token expiry
    expire = datetime.now(UTC) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"sub": str(subject), "exp": int(expire.timestamp())}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    # eagerly load group to avoid lazy-loading (which triggers sync IO)
    q = await db.execute(
        select(User).options(selectinload(User.group)).where(User.id == user_id)
    )  # type: ignore
    return q.scalars().first()


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    """Decode JWT and return subject as int (user id)."""
    try:
        # decode without expiration check;
        # we'll validate exp manually to avoid tz/format issues
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},
        )
    except JWTError as e:
        try:
            unverified = jwt.get_unverified_claims(token)
        except Exception:
            unverified = None
        logger.exception("JWT decode failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"JWT decode failed: {e}; claims={unverified}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # manual exp validation
    exp_val = payload.get("exp")
    if exp_val is not None:
        try:
            exp_dt = datetime.fromtimestamp(float(exp_val), tz=UTC)
        except Exception as e:
            # if exp is malformed, reject
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid exp claim in token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
        if _is_expired(exp_dt):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

    sub_raw = payload.get("sub")
    if sub_raw is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT missing sub claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return int(sub_raw)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid sub claim in token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def admin_required(
    user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency ensuring the user is admin;
    returns the ORM User for callers that need it."""
    user = await get_user_by_id(db, user_id)
    group_name = getattr(user.group, "name", None) if user else None
    if not user or not group_name or group_name != enums.UserGroupEnum.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin required"
        )
    return user


async def get_current_user(
    user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> User:
    """Return ORM User for current token-subject.
    Keeps existing endpoints compatible."""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
