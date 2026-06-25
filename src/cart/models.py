from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


# Models for cart and cart items
class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    user: Mapped[Any] = relationship("User", backref="cart", uselist=False)
    items: Mapped[list[CartItem]] = relationship(
        "CartItem", backref="cart", cascade="all, delete-orphan"
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "movie_id", name="uq_cart_movie"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cart_id: Mapped[int] = mapped_column(
        ForeignKey("carts.id"), nullable=False, index=True
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id"), nullable=False, index=True
    )

    added_at: Mapped[DateTime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    movie: Mapped[Any] = relationship("Movie", backref="cart_items")


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id"),
        nullable=False,
        index=True,
    )

    purchased_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "movie_id",
            name="uq_user_movie_purchase",
        ),
    )

    user: Mapped[Any] = relationship(
        "User",
        backref="purchases",
    )

    movie: Mapped[Any] = relationship(
        "Movie",
        backref="purchases",
    )
