import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.accounts import enums
from src.accounts.enums import UserGroupEnum


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterSchema(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
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
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
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


class ForgotPasswordSchema(BaseModel):
    email: EmailStr


class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
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


class ProfileUpdateSchema(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    avatar: str | None = None
    gender: enums.GenderEnum | None = None
    date_of_birth: datetime | None = None
    info: str | None = None


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    group: enums.UserGroupEnum | None = None

    # Pydantic v2 configuration: read values from ORM attributes
    model_config = ConfigDict(from_attributes=True)


class ActivationResponse(BaseModel):
    activation_token: str

    model_config = ConfigDict(from_attributes=True)


class AccessResponse(BaseModel):
    access_token: str

    model_config = ConfigDict(from_attributes=True)


class ResetResponse(BaseModel):
    reset_token: str

    model_config = ConfigDict(from_attributes=True)


class GroupChangeSchema(BaseModel):
    group: UserGroupEnum
