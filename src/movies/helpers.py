from fastapi import Depends, HTTPException, status

from src.accounts.enums import UserGroupEnum
from src.accounts.helpers import get_current_user
from src.accounts.models import User


async def _ensure_moderator(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.group or current_user.group.name not in (
        UserGroupEnum.MODERATOR.value,
        UserGroupEnum.ADMIN.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Moderator required"
        )
    return current_user
