from pydantic import BaseModel, ConfigDict

from src.general_schemas import StatusResponse


class MovieResponse(BaseModel):
    id: int
    uuid: str
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: int | None = None
    gross: float | None = None
    description: str | None = None
    price: float

    model_config = ConfigDict(from_attributes=True)


class MovieCreate(BaseModel):
    uuid: str | None = None
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: int | None = None
    gross: float | None = None
    description: str | None = None
    price: float
    certification_id: int | None = None
    genres: list[int] | None = None


class MovieUpdate(BaseModel):
    name: str | None = None
    year: int | None = None
    time: int | None = None
    imdb: float | None = None
    votes: int | None = None
    meta_score: int | None = None
    gross: float | None = None
    description: str | None = None
    price: float | None = None
    certification_id: int | None = None
    genres: list[int] | None = None


class CommentResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    parent_id: int | None
    text: str

    model_config = ConfigDict(from_attributes=True)


class CommentCreate(BaseModel):
    text: str
    parent_id: int | None = None


class GenreResponse(BaseModel):
    id: int
    name: str
    movie_count: int

    model_config = ConfigDict(from_attributes=True)


class GenreCreate(BaseModel):
    name: str


class GenreUpdate(BaseModel):
    name: str


class ScoreStatusResponse(StatusResponse):
    score: int

    model_config = ConfigDict(from_attributes=True)
