from __future__ import annotations

from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import User
from src.accounts.routers import get_current_user
from src.cart.models import Cart, CartItem
from src.database import get_db
from src.movies.models import Movie

router = APIRouter()


class CartItemOut(BaseModel):
    id: int
    movie_id: int
    added_at: str


class CartOut(BaseModel):
    items: list[CartItemOut]


@router.get("/", response_model=CartOut)
async def get_cart(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> CartOut:
    q_cart = await db.execute(select(Cart).where(Cart.user_id == current_user.id))
    cart = cast(Cart | None, q_cart.scalars().first())
    if not cart:
        return CartOut(items=[])
    q_items = await db.execute(select(CartItem).where(CartItem.cart_id == cart.id))
    items = cast(list[CartItem], q_items.scalars().all())
    out = [
        CartItemOut(
            id=i.id,
            movie_id=i.movie_id,
            added_at=cast(datetime, i.added_at).isoformat(),
        )
        for i in items
    ]
    return CartOut(items=out)


@router.post("/items", status_code=status.HTTP_201_CREATED, response_model=CartItemOut)
async def add_item(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CartItemOut:
    movie_id = payload.get("movie_id")
    if movie_id is None:
        raise HTTPException(status_code=400, detail="movie_id required")
    # ensure movie exists
    q_movie = await db.execute(select(Movie).where(Movie.id == movie_id))
    movie = cast(Movie | None, q_movie.scalars().first())
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
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
        raise HTTPException(status_code=400, detail="Movie already in cart") from None
    await db.refresh(item)
    return CartItemOut(
        id=item.id,
        movie_id=item.movie_id,
        added_at=cast(datetime, item.added_at).isoformat(),
    )


@router.delete("/items/{movie_id}")
async def remove_item(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    q_cart = await db.execute(select(Cart).where(Cart.user_id == current_user.id))
    cart = cast(Cart | None, q_cart.scalars().first())
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    res = await db.execute(
        delete(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.movie_id == movie_id
        )
    )
    await db.commit()
    affected = getattr(res, "rowcount", 0)
    if affected == 0:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    return {"status": "deleted"}


@router.delete("/clear")
async def clear_cart(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    q_cart = await db.execute(select(Cart).where(Cart.user_id == current_user.id))
    cart = cast(Cart | None, q_cart.scalars().first())
    if not cart:
        return {"status": "cleared"}
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.commit()
    return {"status": "cleared"}
