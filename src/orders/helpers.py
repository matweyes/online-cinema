from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.accounts.enums import UserGroupEnum
from src.accounts.helpers import get_current_user
from src.accounts.models import User
from src.database import get_db
from src.orders.models import Order


async def get_order_with_access(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Order:
    """Load order and verify the current user is the owner or an admin."""
    q = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = q.scalars().first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.user_id != current_user.id:
        group_name = getattr(current_user.group, "name", None)
        if group_name != UserGroupEnum.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

    return order
