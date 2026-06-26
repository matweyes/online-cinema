from pydantic import BaseModel, ConfigDict, Field


class CartItemResponse(BaseModel):
    id: int = Field(..., description="Cart item ID")
    movie_id: int = Field(..., description="Movie ID")
    name: str = Field(..., description="Movie title")
    added_at: str = Field(..., description="ISO 8601 timestamp when item was added")
    year: int = Field(..., description="Movie release year")
    price: float = Field(..., description="Movie price at time of viewing")

    model_config = ConfigDict(from_attributes=True)


class CartResponse(BaseModel):
    items: list[CartItemResponse] = Field(
        ..., description="List of items currently in the cart"
    )

    model_config = ConfigDict(from_attributes=True)


class CartItemCreate(BaseModel):
    movie_id: int = Field(..., description="ID of the movie to add", examples=[1])
