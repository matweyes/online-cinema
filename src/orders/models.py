from __future__ import annotations

import enum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class OrderStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=OrderStatusEnum.PENDING.value,
        default=OrderStatusEnum.PENDING.value,
    )
    total_amount: Mapped[Numeric | None] = mapped_column(Numeric(10, 2), nullable=True)

    user: Mapped[Any] = relationship("User", backref="orders")
    items: Mapped[list[OrderItem]] = relationship(
        "OrderItem", backref="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id"), nullable=False, index=True
    )

    price_at_order: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)

    movie: Mapped[Any] = relationship("Movie", backref="order_items")
