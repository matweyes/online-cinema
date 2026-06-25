from pydantic import BaseModel, ConfigDict


class CartItemResponse(BaseModel):
    id: int
    movie_id: int
    name: str
    added_at: str
    year: int
    price: float

    model_config = ConfigDict(from_attributes=True)


class CartResponse(BaseModel):
    items: list[CartItemResponse]

    model_config = ConfigDict(from_attributes=True)


class CartItemCreate(BaseModel):
    movie_id: int
