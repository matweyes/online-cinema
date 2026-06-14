from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.enums import UserGroupEnum
from src.accounts.models import User
from src.accounts.routers import get_current_user
from src.database import get_db
from src.movies.models import Genre, Movie, MovieGenre

router = APIRouter()


class GenreOut(BaseModel):
    id: int
    name: str
    movie_count: int

    model_config = ConfigDict(from_attributes=True)


class GenreCreate(BaseModel):
    name: str


class GenreUpdate(BaseModel):
    name: str


class MovieOut(BaseModel):
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


async def _ensure_moderator(user: User = Depends(get_current_user)) -> User:
    group_name = getattr(user.group, "name", None)
    if (
        not user
        or not group_name
        or group_name
        not in (
            UserGroupEnum.MODERATOR.value,
            UserGroupEnum.ADMIN.value,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Moderator required"
        )
    return user


@router.get("/", response_model=list[GenreOut])
async def list_genres(db: AsyncSession = Depends(get_db)) -> list[GenreOut]:
    stmt = (
        select(Genre, func.count(MovieGenre.movie_id).label("movie_count"))
        .outerjoin(MovieGenre, Genre.id == MovieGenre.genre_id)
        .group_by(Genre.id)
        .order_by(Genre.name)
    )
    r = await db.execute(stmt)
    rows = r.all()
    result: list[GenreOut] = []
    for row in rows:
        g: Genre = row[0]
        count: int = int(row[1] or 0)
        result.append(GenreOut(id=g.id, name=g.name, movie_count=count))
    return result


@router.get("/{genre_id}/movies", response_model=list[MovieOut])
async def movies_by_genre(
    genre_id: int, db: AsyncSession = Depends(get_db)
) -> list[MovieOut]:
    stmt = (
        select(Movie)
        .join(MovieGenre, Movie.id == MovieGenre.movie_id)
        .where(MovieGenre.genre_id == genre_id)
        .order_by(Movie.id)
    )
    r = await db.execute(stmt)
    movies = r.scalars().all()
    # cast ORM Movie list to Pydantic-compatible return type for static checker
    return cast(list[MovieOut], movies)


@router.post("/", response_model=GenreOut, status_code=status.HTTP_201_CREATED)
async def create_genre(
    data: GenreCreate,
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(select(Genre).where(Genre.name == data.name))
    if q.scalars().first():
        raise HTTPException(status_code=400, detail="Genre already exists")
    g = Genre(name=data.name)
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return GenreOut(id=g.id, name=g.name, movie_count=0)


@router.patch("/{genre_id}", response_model=GenreOut)
async def update_genre(
    genre_id: int,
    data: GenreUpdate,
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(select(Genre).where(Genre.id == genre_id))
    g = q.scalars().first()
    if not g:
        raise HTTPException(status_code=404, detail="Genre not found")
    g.name = data.name
    await db.commit()
    await db.refresh(g)
    # compute count
    cq = await db.execute(
        select(func.count(MovieGenre.movie_id)).where(MovieGenre.genre_id == g.id)
    )
    cnt = int(cq.scalars().first() or 0)
    return GenreOut(id=g.id, name=g.name, movie_count=cnt)


@router.delete("/{genre_id}")
async def delete_genre(
    genre_id: int,
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
    # do not allow deletion if genre has movies
    q = await db.execute(select(MovieGenre).where(MovieGenre.genre_id == genre_id))
    if q.scalars().first():
        raise HTTPException(
            status_code=400, detail="Cannot delete genre with associated movies"
        )
    dq = await db.execute(select(Genre).where(Genre.id == genre_id))
    g = dq.scalars().first()
    if not g:
        raise HTTPException(status_code=404, detail="Genre not found")
    await db.execute(delete(Genre).where(Genre.id == genre_id))
    await db.commit()
    return {"status": "deleted"}
