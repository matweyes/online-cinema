from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrderItemResponse(BaseModel):
    id: int
    movie_id: int
    price_at_order: float

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    status: str
    total_amount: float | None
    items: list[OrderItemResponse]

    model_config = ConfigDict(from_attributes=True)
