import enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import relationship

from src.database import Base


class OrderStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    status = Column(
        String(20),
        nullable=False,
        server_default=OrderStatusEnum.PENDING,
        default=OrderStatusEnum.PENDING,
    )
    total_amount = Column(Numeric(10, 2), nullable=True)

    user = relationship("User", backref="orders")
    items = relationship("OrderItem", backref="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False, index=True)

    price_at_order = Column(Numeric(10, 2), nullable=False)

    movie = relationship("Movie", backref="order_items")
