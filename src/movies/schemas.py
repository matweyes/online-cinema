from pydantic import BaseModel, ConfigDict, Field

from src.general_schemas import StatusResponse


class MovieResponse(BaseModel):
    id: int = Field(..., description="Movie ID")
    uuid: str = Field(..., description="Unique identifier (UUID)")
    name: str = Field(..., description="Movie title")
    year: int = Field(..., description="Release year")
    time: int = Field(..., description="Duration in minutes")
    imdb: float = Field(..., description="IMDb rating")
    votes: int = Field(..., description="Number of IMDb votes")
    meta_score: int | None = Field(None, description="Metascore (0-100)")
    gross: float | None = Field(None, description="Box office gross revenue")
    description: str | None = Field(None, description="Movie description / synopsis")
    price: float = Field(..., description="Purchase price")

    model_config = ConfigDict(from_attributes=True)


class MovieCreate(BaseModel):
    uuid: str | None = Field(
        None, description="Custom UUID (auto-generated if omitted)"
    )
    name: str = Field(..., description="Movie title", examples=["Inception"])
    year: int = Field(..., description="Release year", examples=[2010])
    time: int = Field(..., description="Duration in minutes", examples=[148])
    imdb: float = Field(..., description="IMDb rating (0-10)", examples=[8.8])
    votes: int = Field(..., description="Number of votes", examples=[2000000])
    meta_score: int | None = Field(None, description="Metascore (0-100)", examples=[74])
    gross: float | None = Field(None, description="Box office gross revenue")
    description: str | None = Field(None, description="Movie synopsis")
    price: float = Field(..., description="Purchase price", examples=[9.99])
    certification_id: int | None = Field(None, description="Certification ID (FK)")
    genres: list[int] | None = Field(None, description="List of genre IDs to associate")


class MovieUpdate(BaseModel):
    name: str | None = Field(None, description="Movie title")
    year: int | None = Field(None, description="Release year")
    time: int | None = Field(None, description="Duration in minutes")
    imdb: float | None = Field(None, description="IMDb rating (0-10)")
    votes: int | None = Field(None, description="Number of votes")
    meta_score: int | None = Field(None, description="Metascore (0-100)")
    gross: float | None = Field(None, description="Box office gross revenue")
    description: str | None = Field(None, description="Movie synopsis")
    price: float | None = Field(None, description="Purchase price")
    certification_id: int | None = Field(None, description="Certification ID (FK)")
    genres: list[int] | None = Field(
        None, description="Replace genre associations with these IDs"
    )


class CommentResponse(BaseModel):
    id: int = Field(..., description="Comment ID")
    user_id: int = Field(..., description="Author user ID")
    movie_id: int = Field(..., description="Movie this comment belongs to")
    parent_id: int | None = Field(None, description="Parent comment ID (for replies)")
    text: str = Field(..., description="Comment text")

    model_config = ConfigDict(from_attributes=True)


class CommentCreate(BaseModel):
    text: str = Field(..., description="Comment text", examples=["Great movie!"])
    parent_id: int | None = Field(None, description="Parent comment ID to reply to")


class GenreResponse(BaseModel):
    id: int = Field(..., description="Genre ID")
    name: str = Field(..., description="Genre name")
    movie_count: int = Field(..., description="Number of movies in this genre")

    model_config = ConfigDict(from_attributes=True)


class GenreCreate(BaseModel):
    name: str = Field(
        ..., description="Genre name (must be unique)", examples=["Action"]
    )


class GenreUpdate(BaseModel):
    name: str = Field(..., description="New genre name", examples=["Thriller"])


class ScoreStatusResponse(StatusResponse):
    score: int = Field(..., description="The rating score that was submitted")

    model_config = ConfigDict(from_attributes=True)
