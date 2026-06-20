# Add Movies API router: list, detail, CRUD, comments
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User
from src.accounts.helpers import get_current_user
from src.cart.models import CartItem
from src.database import get_db
from src.general_schemas import StatusResponse
from src.movies.helpers import _ensure_moderator
from src.movies.models import (
    Comment,
    Genre,
    Movie,
    MovieDirector,
    MovieGenre,
    MovieStar,
)
from src.movies.schemas import (
    CommentCreate,
    CommentResponse,
    MovieCreate,
    MovieResponse,
    MovieUpdate,
    ScoreStatusResponse,
)
from src.orders.models import OrderItem

router = APIRouter()


@router.get("/", response_model=list[MovieResponse])
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
@router.get("/favorites", response_model=list[MovieResponse])
async def list_favorites(current_user: User = Depends(get_current_user)):
    # favorites not persisted yet; return empty list
    return []


@router.post("/comments/{comment_id}/likes", response_model=StatusResponse)
async def like_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # not persisted yet
    r = await db.execute(select(Comment).where(Comment.id == comment_id))
    if not r.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )
    return StatusResponse(status="liked")


@router.get("/{movie_id}", response_model=MovieResponse)
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = r.scalars().first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found"
        )
    return movie


@router.post("/", response_model=MovieResponse, status_code=status.HTTP_201_CREATED)
async def create_movie(
    payload: MovieCreate,
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
    """Create a movie."""
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
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Genres not found: {sorted(missing)}",
            )
        for gid in payload.genres:
            mg = MovieGenre(movie_id=m.id, genre_id=gid)
            db.add(mg)
        await db.commit()
        await db.refresh(m)
    return m


@router.patch("/{movie_id}", response_model=MovieResponse)
async def update_movie(
    movie_id: int,
    payload: MovieUpdate,
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = r.scalars().first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found"
        )
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
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Genres not found: {sorted(missing)}",
                    )
                for gid in value:
                    db.add(MovieGenre(movie_id=movie.id, genre_id=gid))
        else:
            setattr(movie, field, value)
    await db.commit()
    await db.refresh(movie)
    return movie


@router.delete("/{movie_id}", response_model=StatusResponse)
async def delete_movie(
    movie_id: int,
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = r.scalars().first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found"
        )
    # check purchased
    q = await db.execute(select(OrderItem).where(OrderItem.movie_id == movie.id))
    if q.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete bought movie"
        )
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
    return StatusResponse(status="deleted")


@router.post("/{movie_id}/likes", response_model=StatusResponse)
async def like_movie(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Placeholder: liking not persisted yet
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    if not r.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found"
        )
    return StatusResponse(status="liked")


@router.get("/{movie_id}/comments", response_model=list[CommentResponse])
async def list_comments(movie_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(Comment).where(Comment.movie_id == movie_id).order_by(Comment.id)
    )
    return r.scalars().all()


@router.post(
    "/{movie_id}/comments",
    response_model=CommentResponse,
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found"
        )
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


@router.post("/{movie_id}/rate", response_model=ScoreStatusResponse)
async def rate_movie(
    movie_id: int,
    score: int = Body(..., ge=1, le=10),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # rating storage not implemented; return OK if movie exists
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    if not r.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found"
        )
    return ScoreStatusResponse(status="rated", score=score)


@router.post("/{movie_id}/favorites", response_model=StatusResponse)
async def add_favorite(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    if not r.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found"
        )
    return StatusResponse(status="favorited")


@router.delete("/{movie_id}/favorites", response_model=StatusResponse)
async def remove_favorite(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    if not r.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found"
        )
    return StatusResponse(status="unfavorited")
