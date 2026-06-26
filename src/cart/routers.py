from __future__ import annotations

from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.accounts.helpers import get_current_user
from src.accounts.models import User
from src.cart.models import Cart, CartItem, Purchase
from src.cart.schemas import CartItemCreate, CartItemResponse, CartResponse
from src.database import get_db
from src.general_schemas import StatusResponse
from src.movies.models import Movie

router = APIRouter()


@router.get(
    "/",
    response_model=CartResponse,
    summary="View cart",
    description="Return the current user's shopping cart with all items, "
    "including movie name, year, and price.",
)
async def get_cart(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> CartResponse:
    q_cart = await db.execute(select(Cart).where(Cart.user_id == current_user.id))
    cart = cast(Cart | None, q_cart.scalars().first())
    if not cart:
        return CartResponse(items=[])
    q_items = await db.execute(
        select(CartItem)
        .options(selectinload(CartItem.movie))
        .where(CartItem.cart_id == cart.id)
    )
    items = cast(list[CartItem], q_items.scalars().all())
    out = [
        CartItemResponse(
            id=i.id,
            movie_id=i.movie_id,
            name=i.movie.name,
            year=i.movie.year,
            price=float(i.movie.price),
            added_at=cast(datetime, i.added_at).isoformat(),
        )
        for i in items
    ]
    return CartResponse(items=out)


@router.post(
    "/items",
    status_code=status.HTTP_201_CREATED,
    response_model=CartItemResponse,
    summary="Add item to cart",
    description="Add a movie to the cart. Fails if the movie is already in the "
    "cart or has been purchased previously.",
    responses={
        400: {"description": "Movie already in cart or already purchased"},
        404: {"description": "Movie not found"},
    },
)
async def add_item(
    payload: CartItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    movie_id = payload.movie_id
    # ensure movie exists
    q_movie = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = cast(Movie | None, q_movie.scalars().first())
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found"
        )
    # ensure movie not already purchased
    already_purchased = await db.scalar(
        select(Purchase).where(
            Purchase.user_id == current_user.id,
            Purchase.movie_id == movie_id,
        )
    )

    if already_purchased:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie already purchased",
        )
    # ensure cart exists
    q_cart = await db.execute(select(Cart).where(Cart.user_id == current_user.id))
    cart = cast(Cart | None, q_cart.scalars().first())
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
    item = CartItem(cart_id=cart.id, movie_id=movie_id)
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Movie already in cart"
        ) from None
    await db.refresh(item)
    return CartItemResponse(
        id=item.id,
        movie_id=item.movie_id,
        name=movie.name,
        year=movie.year,
        price=float(str(movie.price)),
        added_at=cast(datetime, item.added_at).isoformat(),
    )


@router.delete(
    "/items/{movie_id}",
    response_model=StatusResponse,
    summary="Remove item from cart",
    description="Remove a specific movie from the cart by its movie ID.",
    responses={
        404: {"description": "Cart or item not found"},
    },
)
async def remove_item(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q_cart = await db.execute(select(Cart).where(Cart.user_id == current_user.id))
    cart = cast(Cart | None, q_cart.scalars().first())
    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found"
        )
    res = await db.execute(
        delete(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.movie_id == movie_id
        )
    )
    await db.commit()
    affected = getattr(res, "rowcount", 0)
    if affected == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found in cart"
        )
    return StatusResponse(status="deleted")


@router.delete(
    "/items",
    response_model=StatusResponse,
    summary="Clear cart",
    description="Remove all items from the current user's cart.",
)
async def clear_cart(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    q_cart = await db.execute(select(Cart).where(Cart.user_id == current_user.id))
    cart = cast(Cart | None, q_cart.scalars().first())
    if not cart:
        return StatusResponse(status="cleared")
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.commit()
    return StatusResponse(status="cleared")
