from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User
from src.database import get_db
from src.general_schemas import StatusResponse
from src.movies.helpers import _ensure_moderator
from src.movies.models import Genre, Movie, MovieGenre
from src.movies.schemas import GenreCreate, GenreResponse, GenreUpdate, MovieResponse

router = APIRouter()


@router.get(
    "/",
    response_model=list[GenreResponse],
    summary="List genres",
    description="Retrieve all genres with the number of associated movies.",
)
async def list_genres(db: AsyncSession = Depends(get_db)) -> list[GenreResponse]:
    stmt = (
        select(Genre, func.count(MovieGenre.movie_id).label("movie_count"))
        .outerjoin(MovieGenre, Genre.id == MovieGenre.genre_id)
        .group_by(Genre.id)
        .order_by(Genre.name)
    )
    r = await db.execute(stmt)
    rows = r.all()
    result: list[GenreResponse] = []
    for row in rows:
        g: Genre = row[0]
        count: int = int(row[1] or 0)
        result.append(GenreResponse(id=g.id, name=g.name, movie_count=count))
    return result


@router.get(
    "/{genre_id}/movies",
    response_model=list[MovieResponse],
    summary="List movies by genre",
    description="Retrieve all movies that belong to the specified genre.",
)
async def movies_by_genre(
    genre_id: int, db: AsyncSession = Depends(get_db)
) -> list[MovieResponse]:
    stmt = (
        select(Movie)
        .join(MovieGenre, Movie.id == MovieGenre.movie_id)
        .where(MovieGenre.genre_id == genre_id)
        .order_by(Movie.id)
    )
    r = await db.execute(stmt)
    movies = r.scalars().all()
    # cast ORM Movie list to Pydantic-compatible return type for static checker
    return cast(list[MovieResponse], movies)


@router.post(
    "/",
    response_model=GenreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a genre",
    description="Create a new genre. Name must be unique. "
    "Requires **moderator** or **admin** role.",
    responses={
        400: {"description": "Genre with this name already exists"},
        403: {"description": "Moderator role required"},
    },
)
async def create_genre(
    data: GenreCreate,
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(select(Genre).where(Genre.name == data.name))
    if q.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Genre already exists"
        )
    g = Genre(name=data.name)
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return GenreResponse(id=g.id, name=g.name, movie_count=0)


@router.patch(
    "/{genre_id}",
    response_model=GenreResponse,
    summary="Update a genre",
    description="Rename a genre. Requires **moderator** or **admin** role.",
    responses={
        403: {"description": "Moderator role required"},
        404: {"description": "Genre not found"},
    },
)
async def update_genre(
    genre_id: int,
    data: GenreUpdate,
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(select(Genre).where(Genre.id == genre_id))
    g = q.scalars().first()
    if not g:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Genre not found"
        )
    g.name = data.name
    await db.commit()
    await db.refresh(g)
    # compute count
    cq = await db.execute(
        select(func.count(MovieGenre.movie_id)).where(MovieGenre.genre_id == g.id)
    )
    cnt = int(cq.scalars().first() or 0)
    return GenreResponse(id=g.id, name=g.name, movie_count=cnt)


@router.delete(
    "/{genre_id}",
    response_model=StatusResponse,
    summary="Delete a genre",
    description="Delete a genre. Cannot delete genres that have associated movies. "
    "Requires **moderator** or **admin** role.",
    responses={
        400: {"description": "Genre has associated movies"},
        403: {"description": "Moderator role required"},
        404: {"description": "Genre not found"},
    },
)
async def delete_genre(
    genre_id: int,
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
    # do not allow deletion if genre has movies
    q = await db.execute(select(MovieGenre).where(MovieGenre.genre_id == genre_id))
    if q.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete genre with associated movies",
        )
    dq = await db.execute(select(Genre).where(Genre.id == genre_id))
    g = dq.scalars().first()
    if not g:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Genre not found"
        )
    await db.execute(delete(Genre).where(Genre.id == genre_id))
    await db.commit()
    return StatusResponse(status="deleted")
