from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.accounts.helpers import admin_required, get_current_user
from src.cart.models import Cart, CartItem, Purchase
from src.database import get_db
from src.general_schemas import StatusResponse
from src.orders.helpers import get_order_with_access
from src.orders.models import Order, OrderItem, OrderStatusEnum
from src.orders.schemas import OrderResponse

if TYPE_CHECKING:
    from src.accounts.models import User  # for type checking only


router = APIRouter()


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create order from cart",
    description="Convert the current user's cart into an order. "
    "All cart items become order items, the cart is cleared, and the order "
    "is created with status `pending`.",
    responses={
        400: {"description": "Cart is empty or contains invalid movies"},
    },
)
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
        total += Decimal(str(item.movie.price))

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


@router.get(
    "/",
    response_model=list[OrderResponse],
    summary="List my orders",
    description="Retrieve all orders for the authenticated user.",
)
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


@router.get(
    "/admin/all",
    response_model=list[OrderResponse],
    summary="List all orders (admin)",
    description="Retrieve all orders across all users. "
    "Supports optional filtering by status and/or user ID. "
    "Requires **admin** role.",
    responses={
        403: {"description": "Admin role required"},
    },
)
async def admin_all_orders(
    filter_by_status: str | None = Query(
        None, description="Filter by order status (pending / paid / canceled)"
    ),
    filter_by_user_id: int | None = Query(None, description="Filter by user ID"),
    _admin=Depends(admin_required),
    db: AsyncSession = Depends(get_db),
) -> list[Order]:
    q_stmt = select(Order).options(selectinload(Order.items))
    if filter_by_status is not None:
        q_stmt = q_stmt.where(Order.status == filter_by_status)
    if filter_by_user_id is not None:
        q_stmt = q_stmt.where(Order.user_id == filter_by_user_id)
    q = await db.execute(q_stmt)
    orders = list(q.scalars().all())
    return orders


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order details",
    description="Retrieve a single order by ID. "
    "Accessible by the order owner or an admin.",
    responses={
        403: {"description": "Not the order owner and not an admin"},
        404: {"description": "Order not found"},
    },
)
async def get_order(
    order: Order = Depends(get_order_with_access),
) -> Order:
    return order


@router.post(
    "/{order_id}/cancel",
    response_model=StatusResponse,
    summary="Cancel an order",
    description="Cancel a pending order. "
    "Only orders with status `pending` can be canceled.",
    responses={
        400: {"description": "Order is not in pending status"},
        403: {"description": "Not the order owner and not an admin"},
        404: {"description": "Order not found"},
    },
)
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


@router.post(
    "/{order_id}/pay",
    response_model=StatusResponse,
    summary="Pay for an order",
    description="Mark a pending order as paid. Creates purchase records for each movie "
    "in the order, preventing those movies from being added to a cart again.",
    responses={
        400: {"description": "Order is not in pending status"},
        403: {"description": "Not the order owner and not an admin"},
        404: {"description": "Order not found"},
    },
)
async def pay_order(
    order: Order = Depends(get_order_with_access),
    db: AsyncSession = Depends(get_db),
):
    if order.status != OrderStatusEnum.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending orders can be paid",
        )
    # load order items to create purchase records
    q = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    order_items = q.scalars().all()
    for oi in order_items:
        db.add(Purchase(user_id=order.user_id, movie_id=oi.movie_id))

    order.status = OrderStatusEnum.PAID.value
    await db.commit()
    return StatusResponse(status="paid")
