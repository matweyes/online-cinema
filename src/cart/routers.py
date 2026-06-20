from __future__ import annotations

from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User
from src.accounts.helpers import get_current_user
from src.cart.models import Cart, CartItem
from src.cart.schemas import CartItemCreate, CartItemResponse, CartResponse
from src.database import get_db
from src.general_schemas import StatusResponse
from src.movies.models import Movie

router = APIRouter()


@router.get("/", response_model=CartResponse)
async def get_cart(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> CartResponse:
    q_cart = await db.execute(select(Cart).where(Cart.user_id == current_user.id))
    cart = cast(Cart | None, q_cart.scalars().first())
    if not cart:
        return CartResponse(items=[])
    q_items = await db.execute(select(CartItem).where(CartItem.cart_id == cart.id))
    items = cast(list[CartItem], q_items.scalars().all())
    out = [
        CartItemResponse(
            id=i.id,
            movie_id=i.movie_id,
            added_at=cast(datetime, i.added_at).isoformat(),
        )
        for i in items
    ]
    return CartResponse(items=out)


@router.post(
    "/items", status_code=status.HTTP_201_CREATED, response_model=CartItemResponse
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
        added_at=cast(datetime, item.added_at).isoformat(),
    )


@router.delete("/items/{movie_id}", response_model=StatusResponse)
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


@router.delete("/items", response_model=StatusResponse)
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
