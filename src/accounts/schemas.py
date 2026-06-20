from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.accounts import enums


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


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
    group: str
