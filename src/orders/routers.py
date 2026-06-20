from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.accounts.helpers import admin_required, get_current_user
from src.cart.models import Cart, CartItem
from src.database import get_db
from src.general_schemas import StatusResponse
from src.orders.helpers import get_order_with_access
from src.orders.models import Order, OrderItem, OrderStatusEnum
from src.orders.schemas import OrderResponse

if TYPE_CHECKING:
    from src.accounts.models import User  # for type checking only


router = APIRouter()


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty"
        )

    # compute total
    total = Decimal("0.00")
    for item in cart.items:
        if not item.movie or item.movie.price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid movie in cart"
            )
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
    # Return ORM object and let FastAPI/response_model handle serialization
    return order_out


@router.get("/", response_model=list[OrderResponse])
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


@router.get("/admin/all", response_model=list[OrderResponse])
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


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order: Order = Depends(get_order_with_access),
) -> Order:
    return order


@router.post("/{order_id}/cancel", response_model=StatusResponse)
async def cancel_order(
    order: Order = Depends(get_order_with_access),
    db: AsyncSession = Depends(get_db),
):
    if order.status != OrderStatusEnum.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending orders can be canceled",
        )
    order.status = OrderStatusEnum.CANCELED.value
    await db.commit()
    return StatusResponse(status="canceled")


@router.post("/{order_id}/pay", response_model=StatusResponse)
async def pay_order(
    order: Order = Depends(get_order_with_access),
    db: AsyncSession = Depends(get_db),
):
    if order.status != OrderStatusEnum.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending orders can be paid",
        )
    order.status = OrderStatusEnum.PAID.value
    await db.commit()
    return StatusResponse(status="paid")
