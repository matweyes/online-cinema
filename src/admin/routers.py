from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.helpers import admin_required
from src.accounts.models import User, UserGroup
from src.accounts.schemas import GroupChangeSchema
from src.database import get_db
from src.general_schemas import StatusResponse

router = APIRouter()


@router.patch("/users/{user_id}/group", response_model=StatusResponse)
async def change_user_group(
    user_id: int,
    data: GroupChangeSchema,
    _admin: User = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(select(User).where(User.id == user_id))
    user = q.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    qg = await db.execute(select(UserGroup).where(UserGroup.name == data.group))
    group = qg.scalars().first()
    if not group:
        group = UserGroup(name=data.group)
        db.add(group)
        await db.commit()
        await db.refresh(group)
    user.group_id = cast(int, group.id)
    await db.commit()
    return StatusResponse(status="group_changed")


@router.patch("/users/{user_id}/activation", response_model=StatusResponse)
async def manual_activate(
    user_id: int,
    _admin: User = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(select(User).where(User.id == user_id))
    user = q.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    user.is_active = True
    await db.commit()
    return StatusResponse(status="activated")
