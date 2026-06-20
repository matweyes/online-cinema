from pydantic import BaseModel, ConfigDict


class CartItemResponse(BaseModel):
    id: int
    movie_id: int
    added_at: str

    model_config = ConfigDict(from_attributes=True)


class CartResponse(BaseModel):
    items: list[CartItemResponse]

    model_config = ConfigDict(from_attributes=True)


class CartItemCreate(BaseModel):
    movie_id: int
