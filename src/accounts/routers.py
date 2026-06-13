"""
Accounts API router: registration, activation, auth, profile management.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
import logging

from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts import enums
from src.accounts.models import (
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserGroup,
    UserProfile,
)
from src.database import get_db
from src.config import settings

router = APIRouter()

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/accounts/login")

logger = logging.getLogger(__name__)


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: int
    exp: int


class RegisterSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class ActivateSchema(BaseModel):
    token: str


class ResendActivationSchema(BaseModel):
    email: EmailStr


class LoginSchema(BaseModel):
    username: EmailStr
    password: str


class LogoutSchema(BaseModel):
    refresh_token: str


class RefreshSchema(BaseModel):
    refresh_token: str


class ChangePasswordSchema(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


class ForgotPasswordSchema(BaseModel):
    email: EmailStr


class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str = Field(min_length=6)


class ProfileUpdateSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar: Optional[str] = None
    gender: Optional[enums.GenderEnum] = None
    date_of_birth: Optional[datetime] = None
    info: Optional[str] = None


class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    group: Optional[enums.UserGroupEnum] = None

    # Pydantic v2 configuration: read values from ORM attributes
    model_config = ConfigDict(from_attributes=True)


def _truncate_password(pw: str) -> str:
    """Truncate password to 72 bytes (bcrypt limit) preserving UTF-8 characters."""
    b = pw.encode("utf-8", errors="ignore")
    if len(b) <= 72:
        return pw
    tb = b[:72]
    return tb.decode("utf-8", errors="ignore")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_truncate_password(plain), hashed)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(_truncate_password(password))


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Return datetime as UTC-aware. If dt is naive, assume UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_expired(dt: Optional[datetime]) -> bool:
    """Return True if dt is None or dt is before now (UTC).

    SQLite stores timestamps without tzinfo; normalize both sides to naive UTC
    datetimes for comparison to avoid offset-naive vs offset-aware errors.
    """
    if dt is None:
        return True

    # convert to aware UTC and compare timestamps
    try:
        left_aware = _ensure_aware(dt)
    except Exception:
        return True
    right_ts = datetime.now(timezone.utc).timestamp()
    return left_aware.timestamp() < right_ts


def create_access_token(subject: int, expires_delta: Optional[timedelta] = None) -> str:
    # use timezone-aware UTC for token expiry
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"sub": str(subject), "exp": int(expire.timestamp())}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    # eagerly load group and profile to avoid lazy-loading (which triggers sync IO)
    q = await db.execute(select(User).options(selectinload(User.group), selectinload(User.profile)).where(User.id == user_id))  # type: ignore
    return q.scalars().first()


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    """Decode JWT and return subject as int (user id)."""
    try:
        # decode without expiration check; we'll validate exp manually to avoid tz/format issues
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_exp": False})
    except JWTError as e:
        try:
            unverified = jwt.get_unverified_claims(token)
        except Exception:
            unverified = None
        logger.exception("JWT decode failed: %s", e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"JWT decode failed: {e}; claims={unverified}", headers={"WWW-Authenticate": "Bearer"})

    # manual exp validation
    exp_val = payload.get("exp")
    if exp_val is not None:
        try:
            exp_dt = datetime.fromtimestamp(float(exp_val), tz=timezone.utc)
        except Exception:
            # if exp is malformed, reject
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid exp claim in token", headers={"WWW-Authenticate": "Bearer"})
        if _is_expired(exp_dt):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired", headers={"WWW-Authenticate": "Bearer"})

    sub_raw = payload.get("sub")
    if sub_raw is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT missing sub claim", headers={"WWW-Authenticate": "Bearer"})
    try:
        return int(sub_raw)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid sub claim in token", headers={"WWW-Authenticate": "Bearer"})


async def admin_required(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)) -> User:
    """Dependency ensuring the user is admin; returns the ORM User for callers that need it."""
    user = await get_user_by_id(db, user_id)
    if not user or not user.group or user.group.name != enums.UserGroupEnum.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


async def get_current_user(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)) -> User:
    """Return ORM User for current token-subject. Keeps existing endpoints compatible."""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found", headers={"WWW-Authenticate": "Bearer"})
    return user


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterSchema, db: AsyncSession = Depends(get_db)) -> dict:
    q = await db.execute(select(User).where(User.email == data.email))  # type: ignore
    if q.scalars().first():
        raise HTTPException(status_code=400, detail="User already exists")

    # ensure user group exists
    qg = await db.execute(select(UserGroup).where(UserGroup.name == enums.UserGroupEnum.USER.value))  # type: ignore
    group = qg.scalars().first()
    if not group:
        group = UserGroup(name=enums.UserGroupEnum.USER.value)
        db.add(group)
        await db.commit()
        await db.refresh(group)

    user = User(email=data.email, hashed_password=get_password_hash(data.password), is_active=False, group_id=group.id)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token_str = uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS)
    activation = ActivationToken(user_id=user.id, token=token_str, expires_at=expires)
    db.add(activation)
    await db.commit()

    # In production, send email. Here return token for tests/dev.
    return {"activation_token": token_str}


@router.post("/activate")
async def activate(data: ActivateSchema, db: AsyncSession = Depends(get_db)) -> dict:
    q = await db.execute(select(ActivationToken).where(ActivationToken.token == data.token))  # type: ignore
    at = q.scalars().first()
    if not at or _is_expired(at.expires_at):
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    q = await db.execute(select(User).where(User.id == at.user_id))  # type: ignore
    user = q.scalars().first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    user.is_active = True
    await db.delete(at)
    await db.commit()
    return {"status": "activated"}


@router.post("/resend-activation")
async def resend_activation(data: ResendActivationSchema, db: AsyncSession = Depends(get_db)) -> dict:
    q = await db.execute(select(User).where(User.email == data.email))  # type: ignore
    user = q.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_active:
        raise HTTPException(status_code=400, detail="User already active")
    # remove old token
    await db.execute(delete(ActivationToken).where(ActivationToken.user_id == user.id))  # type: ignore
    token_str = uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS)
    activation = ActivationToken(user_id=user.id, token=token_str, expires_at=expires)
    db.add(activation)
    await db.commit()
    return {"activation_token": token_str}


@router.post("/login", response_model=Token)
async def login(data: LoginSchema, db: AsyncSession = Depends(get_db)) -> Token:
    q = await db.execute(select(User).where(User.email == data.username))  # type: ignore
    user = q.scalars().first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")

    access_token = create_access_token(user.id)
    refresh_token_str = uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(user_id=user.id, token=refresh_token_str, expires_at=expires)
    db.add(rt)
    await db.commit()

    return Token(access_token=access_token, refresh_token=refresh_token_str)


@router.post("/logout")
async def logout(data: LogoutSchema, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(delete(RefreshToken).where(RefreshToken.token == data.refresh_token, RefreshToken.user_id == current_user.id))  # type: ignore
    await db.commit()
    return {"status": "logged_out"}


@router.post("/refresh", response_model=dict)
async def refresh(data: RefreshSchema, db: AsyncSession = Depends(get_db)) -> dict:
    q = await db.execute(select(RefreshToken).where(RefreshToken.token == data.refresh_token))  # type: ignore
    rt = q.scalars().first()
    if not rt or _is_expired(rt.expires_at):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    access_token = create_access_token(rt.user_id)
    return {"access_token": access_token}


@router.post("/change-password")
async def change_password(data: ChangePasswordSchema, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Old password mismatch")
    current_user.hashed_password = get_password_hash(data.new_password)
    await db.commit()
    return {"status": "password_changed"}


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordSchema, db: AsyncSession = Depends(get_db)) -> dict:
    q = await db.execute(select(User).where(User.email == data.email))  # type: ignore
    user = q.scalars().first()
    if not user:
        # do not reveal user existence
        return {"status": "ok"}
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))  # type: ignore
    token_str = uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    prt = PasswordResetToken(user_id=user.id, token=token_str, expires_at=expires)
    db.add(prt)
    await db.commit()
    return {"reset_token": token_str}


@router.post("/reset-password")
async def reset_password(data: ResetPasswordSchema, db: AsyncSession = Depends(get_db)) -> dict:
    q = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token == data.token))  # type: ignore
    prt = q.scalars().first()
    if not prt or _is_expired(prt.expires_at):
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    q = await db.execute(select(User).where(User.id == prt.user_id))  # type: ignore
    user = q.scalars().first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    user.hashed_password = get_password_hash(data.new_password)
    await db.delete(prt)
    await db.commit()
    return {"status": "password_reset"}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    # convert stored group name (string) to UserGroupEnum for Pydantic validation/serialization
    group_enum = None
    if current_user.group and current_user.group.name:
        try:
            group_enum = enums.UserGroupEnum(current_user.group.name)
        except Exception:
            group_enum = None
    return UserOut(id=current_user.id, email=current_user.email, is_active=current_user.is_active, group=group_enum)


@router.patch("/me/profile")
async def update_profile(data: ProfileUpdateSchema, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """Update current user's profile using validated Pydantic schema."""
    q = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))  # type: ignore
    profile = q.scalars().first()
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    # apply validated fields
    payload = data
    if payload.first_name is not None:
        profile.first_name = payload.first_name
    if payload.last_name is not None:
        profile.last_name = payload.last_name
    if payload.avatar is not None:
        profile.avatar = payload.avatar
    if payload.gender is not None:
        # store string value in DB (SQLite)
        profile.gender = payload.gender.value
    if payload.date_of_birth is not None:
        profile.date_of_birth = payload.date_of_birth
    if payload.info is not None:
        profile.info = payload.info

    await db.commit()
    return {"status": "profile_updated"}


class GroupChangeSchema(BaseModel):
    group: enums.UserGroupEnum


@router.patch("/users/{user_id}/group")
async def change_user_group(user_id: int, data: GroupChangeSchema, _admin: User = Depends(admin_required), db: AsyncSession = Depends(get_db)) -> dict:
    q = await db.execute(select(User).where(User.id == user_id))  # type: ignore
    user = q.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    qg = await db.execute(select(UserGroup).where(UserGroup.name == data.group.value))  # type: ignore
    group = qg.scalars().first()
    if not group:
        group = UserGroup(name=data.group.value)
        db.add(group)
        await db.commit()
        await db.refresh(group)
    user.group_id = group.id
    await db.commit()
    return {"status": "group_changed"}


@router.patch("/users/{user_id}/activate")
async def manual_activate(user_id: int, _admin: User = Depends(admin_required), db: AsyncSession = Depends(get_db)) -> dict:
    q = await db.execute(select(User).where(User.id == user_id))  # type: ignore
    user = q.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    await db.commit()
    return {"status": "activated"}
