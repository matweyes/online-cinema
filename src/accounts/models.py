# Модель SQLAlchemy для таблиц аккаунтов
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship

from src.database import Base


class UserGroup(Base):
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True, index=True)
    # SQLite does not support ENUM - store as String, validation on Pydantic level
    name = Column(String(50), unique=True, nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="0", default=False)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    group_id = Column(Integer, ForeignKey("user_groups.id"), nullable=False)
    group = relationship("UserGroup", backref="users")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    first_name = Column(String(100))
    last_name = Column(String(100))
    avatar = Column(String(255))
    # gender is stored as String, values from enums.GenderEnum
    gender = Column(String(20))
    date_of_birth = Column(DateTime)
    info = Column(Text)

    user = relationship("User", backref="profile", uselist=False)


class ActivationToken(Base):
    __tablename__ = "activation_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", backref="activation_token", uselist=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", backref="password_reset_token", uselist=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", backref="refresh_tokens")
