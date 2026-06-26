import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.accounts import enums
from src.accounts.enums import UserGroupEnum


def _validate_password_complexity(value: str) -> str:
    """Shared password-complexity rules used by multiple schemas."""
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", value):
        raise ValueError("Password must contain at least one lowercase letter")

    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one digit")

    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", value):
        raise ValueError("Password must contain at least one special character")

    if re.search(r"\s", value):
        raise ValueError("Password cannot contain spaces")

    return value


class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="Opaque refresh token")
    token_type: str = Field("bearer", description="Token type (always 'bearer')")


class RegisterSchema(BaseModel):
    email: EmailStr = Field(
        ..., description="User email address", examples=["user@example.com"]
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password "
        "(8-128 chars, must include "
        "uppercase, lowercase, digit, and special character, no spaces)",
        examples=["MyPass_123"],
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_complexity(value)


class ActivateSchema(BaseModel):
    token: str = Field(..., description="Activation token received after registration")


class ResendActivationSchema(BaseModel):
    email: EmailStr = Field(
        ..., description="Email of the inactive account", examples=["user@example.com"]
    )


class LoginSchema(BaseModel):
    username: EmailStr = Field(
        ..., description="User email address", examples=["user@example.com"]
    )
    password: str = Field(..., description="Account password")


class LogoutSchema(BaseModel):
    refresh_token: str = Field(..., description="Refresh token to invalidate")


class RefreshSchema(BaseModel):
    refresh_token: str = Field(..., description="Valid refresh token")


class ChangePasswordSchema(BaseModel):
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password (same complexity rules as registration)",
        examples=["NewPass_456"],
    )

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_complexity(value)


class ForgotPasswordSchema(BaseModel):
    email: EmailStr = Field(
        ..., description="Email of the account to reset", examples=["user@example.com"]
    )


class ResetPasswordSchema(BaseModel):
    token: str = Field(
        ..., description="Password-reset token from forgot-password endpoint"
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password (same complexity rules as registration)",
        examples=["NewPass_789"],
    )

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_complexity(value)


class ProfileUpdateSchema(BaseModel):
    first_name: str | None = Field(None, description="First name", examples=["John"])
    last_name: str | None = Field(None, description="Last name", examples=["Doe"])
    avatar: str | None = Field(
        None, description="Avatar URL", examples=["https://example.com/avatar.png"]
    )
    gender: enums.GenderEnum | None = Field(None, description="Gender (man / woman)")
    date_of_birth: datetime | None = Field(
        None, description="Date of birth (ISO 8601)", examples=["1990-01-15T00:00:00"]
    )
    info: str | None = Field(None, description="Short bio or additional info")


class UserResponse(BaseModel):
    id: int = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    is_active: bool = Field(..., description="Whether the account is activated")
    group: enums.UserGroupEnum | None = Field(
        None, description="User role (user / moderator / admin)"
    )

    # Pydantic v2 configuration: read values from ORM attributes
    model_config = ConfigDict(from_attributes=True)


class ActivationResponse(BaseModel):
    activation_token: str = Field(
        ..., description="Token to activate the account (sent via email in production)"
    )

    model_config = ConfigDict(from_attributes=True)


class AccessResponse(BaseModel):
    access_token: str = Field(..., description="New JWT access token")

    model_config = ConfigDict(from_attributes=True)


class ResetResponse(BaseModel):
    reset_token: str = Field(
        ..., description="Password-reset token (empty string if user not found)"
    )

    model_config = ConfigDict(from_attributes=True)


class GroupChangeSchema(BaseModel):
    group: UserGroupEnum = Field(
        ..., description="Target role (user / moderator / admin)"
    )
