from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderItemResponse(BaseModel):
    id: int = Field(..., description="Order item ID")
    movie_id: int = Field(..., description="Purchased movie ID")
    price_at_order: float = Field(
        ..., description="Price at the time the order was placed"
    )

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: int = Field(..., description="Order ID")
    user_id: int = Field(..., description="Owner user ID")
    created_at: datetime = Field(..., description="Order creation timestamp")
    status: str = Field(..., description="Order status (pending / paid / canceled)")
    total_amount: float | None = Field(None, description="Total order amount")
    items: list[OrderItemResponse] = Field(..., description="Ordered movies")

    model_config = ConfigDict(from_attributes=True)
