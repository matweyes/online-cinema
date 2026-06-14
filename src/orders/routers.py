from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.accounts.routers import admin_required, get_current_user
from src.cart.models import Cart, CartItem
from src.database import get_db
from src.orders.models import Order, OrderItem, OrderStatusEnum

if TYPE_CHECKING:
    from src.accounts.models import User  # for type checking only


router = APIRouter()


class OrderItemOut(BaseModel):
    id: int
    movie_id: int
    price_at_order: float

    model_config = ConfigDict(from_attributes=True)


class OrderOut(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    status: str
    total_amount: float | None
    items: list[OrderItemOut]

    model_config = ConfigDict(from_attributes=True)


@router.post("/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    # load cart with items and movies
    q = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items).selectinload(CartItem.movie))
        .where(Cart.user_id == current_user.id)
    )
    cart = q.scalars().first()
    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # compute total
    total = Decimal("0.00")
    for item in cart.items:
        if not item.movie or item.movie.price is None:
            raise HTTPException(status_code=400, detail="Invalid movie in cart")
        total += Decimal(item.movie.price)

    order = Order(user_id=current_user.id, total_amount=total)
    db.add(order)
    await db.flush()  # get order.id

    # create order items
    for item in cart.items:
        oi = OrderItem(
            order_id=order.id, movie_id=item.movie_id, price_at_order=item.movie.price
        )
        db.add(oi)

    # remove cart items
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))

    await db.commit()
    await db.refresh(order)
    q = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order.id)
    )
    order_out = q.scalars().first()
    return OrderOut.model_validate(order_out).model_dump(mode="json")


@router.get("/", response_model=list[OrderOut])
async def my_orders(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Order]:
    q = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == current_user.id)
    )
    orders = list(q.scalars().all())
    return orders


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Order:
    q = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = q.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    # allow owner or admin
    if order.user_id != current_user.id:
        await admin_required(user_id=current_user.id, db=db)  # will raise if not admin
    return order


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    q = await db.execute(select(Order).where(Order.id == order_id))
    order = q.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        # allow admin to cancel
        await admin_required(user_id=current_user.id, db=db)
    if order.status != OrderStatusEnum.PENDING.value:
        raise HTTPException(
            status_code=400, detail="Only pending orders can be canceled"
        )
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(status=OrderStatusEnum.CANCELED.value)
    )
    await db.commit()
    return {"status": "canceled"}


@router.post("/{order_id}/pay")
async def pay_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    q = await db.execute(select(Order).where(Order.id == order_id))
    order = q.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        # allow admin to mark as paid
        await admin_required(user_id=current_user.id, db=db)
    if order.status != OrderStatusEnum.PENDING.value:
        raise HTTPException(status_code=400, detail="Only pending orders can be paid")
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(status=OrderStatusEnum.PAID.value)
    )
    await db.commit()
    return {"status": "paid"}


@router.get("/admin/all", response_model=list[OrderOut])
async def admin_all_orders(
    status: str | None = None,
    user_id: int | None = None,
    _admin=Depends(admin_required),
    db: AsyncSession = Depends(get_db),
) -> list[Order]:
    q_stmt = select(Order).options(selectinload(Order.items))
    if status:
        q_stmt = q_stmt.where(Order.status == status)
    if user_id:
        q_stmt = q_stmt.where(Order.user_id == user_id)
    q = await db.execute(q_stmt)
    orders = list(q.scalars().all())
    return orders
