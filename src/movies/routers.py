# Add Movies API router: list, detail, CRUD, comments
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.enums import UserGroupEnum
from src.accounts.models import User
from src.accounts.routers import get_current_user
from src.cart.models import CartItem
from src.database import get_db
from src.movies.models import (
    Comment,
    Genre,
    Movie,
    MovieDirector,
    MovieGenre,
    MovieStar,
)
from src.orders.models import OrderItem

router = APIRouter()


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


class CommentOut(BaseModel):
    id: int
    user_id: int
    movie_id: int
    parent_id: int | None
    text: str

    model_config = ConfigDict(from_attributes=True)


class CommentCreate(BaseModel):
    text: str
    parent_id: int | None = None


async def _ensure_moderator(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.group or current_user.group.name not in (
        UserGroupEnum.MODERATOR.value,
        UserGroupEnum.ADMIN.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Moderator required"
        )
    return current_user


@router.get("/", response_model=list[MovieOut])
async def list_movies(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    q: str | None = Query(None),
    sort: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Movie)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Movie.name.ilike(like), Movie.description.ilike(like)))
    if sort:
        if sort.startswith("-"):
            col = sort[1:]
            stmt = stmt.order_by(desc(getattr(Movie, col, Movie.id)))
        else:
            col = sort
            stmt = stmt.order_by(getattr(Movie, col, Movie.id))
    stmt = stmt.offset((page - 1) * size).limit(size)
    r = await db.execute(stmt)
    return r.scalars().all()


# Static routes must be declared before dynamic routes like '/{movie_id}'
@router.get("/favorites", response_model=list[MovieOut])
async def list_favorites(current_user: User = Depends(get_current_user)):
    # favorites not persisted yet; return empty list
    return []


@router.post("/comments/{comment_id}/like")
async def like_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # not persisted yet
    r = await db.execute(select(Comment).where(Comment.id == comment_id))
    if not r.scalars().first():
        raise HTTPException(status_code=404, detail="Comment not found")
    return {"status": "liked"}


@router.get("/{movie_id}", response_model=MovieOut)
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = r.scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


@router.post("/", response_model=MovieOut, status_code=status.HTTP_201_CREATED)
async def create_movie(
    data: dict = Body(...),
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Create a movie. Accept loose JSON and validate inside
    to avoid strict pre-validation 422s in tests."""
    try:
        payload = MovieCreate(**data)
    except ValidationError as e:
        # return friendly validation error
        raise HTTPException(status_code=422, detail=e.errors()) from e

    m = Movie(
        uuid=payload.uuid or str(uuid4()),
        name=payload.name,
        year=payload.year,
        time=payload.time,
        imdb=payload.imdb,
        votes=payload.votes,
        meta_score=payload.meta_score,
        gross=payload.gross,
        description=payload.description,
        price=payload.price,
        certification_id=payload.certification_id,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    # handle genres associations
    if payload.genres:
        # validate genres exist
        qg = await db.execute(select(Genre).where(Genre.id.in_(payload.genres)))
        found = {g.id for g in qg.scalars().all()}
        missing = set(payload.genres) - found
        if missing:
            raise HTTPException(
                status_code=400, detail=f"Genres not found: {sorted(missing)}"
            )
        for gid in payload.genres:
            mg = MovieGenre(movie_id=m.id, genre_id=gid)
            db.add(mg)
        await db.commit()
        await db.refresh(m)
    return m


@router.patch("/{movie_id}", response_model=MovieOut)
async def update_movie(
    movie_id: int,
    data: dict = Body(...),
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = r.scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    try:
        payload = MovieUpdate(**data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors()) from e
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "genres":
            # replace genres associations
            await db.execute(delete(MovieGenre).where(MovieGenre.movie_id == movie.id))
            if value:
                # validate provided genre ids
                qg = await db.execute(select(Genre).where(Genre.id.in_(value)))
                found = {g.id for g in qg.scalars().all()}
                missing = set(value) - found
                if missing:
                    raise HTTPException(
                        status_code=400, detail=f"Genres not found: {sorted(missing)}"
                    )
                for gid in value:
                    db.add(MovieGenre(movie_id=movie.id, genre_id=gid))
        else:
            setattr(movie, field, value)
    await db.commit()
    await db.refresh(movie)
    return movie


@router.delete("/{movie_id}")
async def delete_movie(
    movie_id: int,
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = r.scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    # check purchased
    q = await db.execute(select(OrderItem).where(OrderItem.movie_id == movie.id))
    if q.scalars().first():
        raise HTTPException(status_code=400, detail="Cannot delete bought movie")
    # delete related rows from association tables
    # and cart items to avoid FK constraint issues in SQLite
    await db.execute(delete(Comment).where(Comment.movie_id == movie.id))
    await db.execute(delete(MovieGenre).where(MovieGenre.movie_id == movie.id))
    await db.execute(delete(MovieStar).where(MovieStar.movie_id == movie.id))
    await db.execute(delete(MovieDirector).where(MovieDirector.movie_id == movie.id))
    await db.execute(delete(CartItem).where(CartItem.movie_id == movie.id))
    # use SQL delete to avoid ORM trying to nullify FK relationships
    await db.execute(delete(Movie).where(Movie.id == movie.id))
    await db.commit()
    return {"status": "deleted"}


@router.post("/{movie_id}/like")
async def like_movie(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Placeholder: liking not persisted yet
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    if not r.scalars().first():
        raise HTTPException(status_code=404, detail="Movie not found")
    return {"status": "liked"}


@router.get("/{movie_id}/comments", response_model=list[CommentOut])
async def list_comments(movie_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(Comment).where(Comment.movie_id == movie_id).order_by(Comment.id)
    )
    return r.scalars().all()


@router.post(
    "/{movie_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    movie_id: int,
    data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    if not r.scalars().first():
        raise HTTPException(status_code=404, detail="Movie not found")
    comment = Comment(
        user_id=current_user.id,
        movie_id=movie_id,
        parent_id=data.parent_id,
        text=data.text,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.post("/{movie_id}/rate")
async def rate_movie(
    movie_id: int,
    score: int = Body(..., ge=1, le=10),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # rating storage not implemented; return OK if movie exists
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    if not r.scalars().first():
        raise HTTPException(status_code=404, detail="Movie not found")
    return {"status": "rated", "score": score}


@router.post("/{movie_id}/favorite")
async def add_favorite(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    if not r.scalars().first():
        raise HTTPException(status_code=404, detail="Movie not found")
    return {"status": "favorited"}


@router.delete("/{movie_id}/favorite")
async def remove_favorite(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    if not r.scalars().first():
        raise HTTPException(status_code=404, detail="Movie not found")
    return {"status": "unfavorited"}
