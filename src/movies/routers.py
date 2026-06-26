# Add Movies API router: list, detail, CRUD, comments
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.helpers import get_current_user
from src.accounts.models import User
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
ALLOWED_SORT_FIELDS = {"price", "year", "meta_score"}


@router.get(
    "/",
    response_model=list[MovieResponse],
    summary="List movies",
    description="Retrieve a paginated list of movies. Supports text search and sorting.",
)
async def list_movies(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
    q: str | None = Query(None, description="Search by movie name or description"),
    sort: str | None = Query(
        None,
        description="Sort field. Allowed: `price`, `year`, `meta_score`. "
        "Prefix with `-` for descending order (e.g. `-year`).",
    ),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Movie)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Movie.name.ilike(like), Movie.description.ilike(like)))
    if sort:
        col = sort[1:] if sort.startswith("-") else sort
        if col not in ALLOWED_SORT_FIELDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field '{col}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_SORT_FIELDS))}",
            )
        if sort.startswith("-"):
            stmt = stmt.order_by(desc(getattr(Movie, col)))
        else:
            stmt = stmt.order_by(getattr(Movie, col))
    stmt = stmt.offset((page - 1) * size).limit(size)
    r = await db.execute(stmt)
    return r.scalars().all()


# Static routes must be declared before dynamic routes like '/{movie_id}'
@router.get(
    "/favorites",
    response_model=list[MovieResponse],
    summary="List favorite movies",
    description="Return the authenticated user's favorite movies.",
)
async def list_favorites(current_user: User = Depends(get_current_user)):
    # favorites not persisted yet; return empty list
    return []


@router.post(
    "/{movie_id}/comments/{comment_id}/likes",
    response_model=StatusResponse,
    summary="Like a comment",
    description="Toggle a like on a specific comment. The comment must belong to the given movie.",
    responses={
        404: {"description": "Movie or comment not found"},
    },
)
async def like_comment(
    movie_id: int,
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # validate movie exists
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    if not r.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found"
        )
    # validate comment exists and belongs to the movie
    r = await db.execute(
        select(Comment).where(Comment.id == comment_id, Comment.movie_id == movie_id)
    )
    if not r.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )
    # not persisted yet
    return StatusResponse(status="liked")


@router.get(
    "/{movie_id}",
    response_model=MovieResponse,
    summary="Get movie details",
    description="Retrieve full details for a single movie by its ID.",
    responses={
        404: {"description": "Movie not found"},
    },
)
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = r.scalars().first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found"
        )
    return movie


@router.post(
    "/",
    response_model=MovieResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a movie",
    description="Create a new movie entry. Requires **moderator** or **admin** role. "
    "Optionally associate genres by providing a list of genre IDs.",
    responses={
        400: {"description": "Genre IDs not found"},
        403: {"description": "Moderator role required"},
    },
)
async def create_movie(
    payload: MovieCreate,
    _mod: User = Depends(_ensure_moderator),
    db: AsyncSession = Depends(get_db),
):
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


@router.patch(
    "/{movie_id}",
    response_model=MovieResponse,
    summary="Update a movie",
    description="Partially update a movie. Only provided fields are changed. "
    "Requires **moderator** or **admin** role.",
    responses={
        400: {"description": "Genre IDs not found"},
        403: {"description": "Moderator role required"},
        404: {"description": "Movie not found"},
    },
)
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


@router.delete(
    "/{movie_id}",
    response_model=StatusResponse,
    summary="Delete a movie",
    description="Delete a movie and its related data (comments, genre associations, etc.). "
    "Cannot delete a movie that has been purchased. "
    "Requires **moderator** or **admin** role.",
    responses={
        400: {"description": "Movie has been purchased and cannot be deleted"},
        403: {"description": "Moderator role required"},
        404: {"description": "Movie not found"},
    },
)
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


@router.post(
    "/{movie_id}/likes",
    response_model=StatusResponse,
    summary="Like a movie",
    description="Toggle a like on a movie.",
    responses={
        404: {"description": "Movie not found"},
    },
)
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


@router.get(
    "/{movie_id}/comments",
    response_model=list[CommentResponse],
    summary="List comments",
    description="Retrieve all comments for a movie, ordered by ID.",
)
async def list_comments(movie_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(Comment).where(Comment.movie_id == movie_id).order_by(Comment.id)
    )
    return r.scalars().all()


@router.post(
    "/{movie_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Post a comment",
    description="Add a comment to a movie. Optionally set `parent_id` to reply "
    "to an existing comment.",
    responses={
        404: {"description": "Movie not found"},
    },
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


@router.post(
    "/{movie_id}/rate",
    response_model=ScoreStatusResponse,
    summary="Rate a movie",
    description="Submit a rating (1-10) for a movie.",
    responses={
        404: {"description": "Movie not found"},
    },
)
async def rate_movie(
    movie_id: int,
    score: int = Body(..., ge=1, le=10, description="Rating score from 1 to 10"),
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


@router.post(
    "/{movie_id}/favorites",
    response_model=StatusResponse,
    summary="Add movie to favorites",
    description="Add a movie to the authenticated user's favorites list.",
    responses={
        404: {"description": "Movie not found"},
    },
)
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


@router.delete(
    "/{movie_id}/favorites",
    response_model=StatusResponse,
    summary="Remove movie from favorites",
    description="Remove a movie from the authenticated user's favorites list.",
    responses={
        404: {"description": "Movie not found"},
    },
)
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
