import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.accounts import enums
from src.accounts.models import User, UserGroup
from src.accounts.routers import get_password_hash
from tests.conftest import async_session_test, register_user, login_user


@pytest.mark.asyncio
async def test_admin_change_group_and_activate(client: AsyncClient):
    # register target user (inactive)
    target_email = "target@example.com"
    target_pass = "targetpass"
    _ = await register_user(client, target_email, target_pass)

    # create admin user directly in DB
    admin_email = "admin@example.com"
    admin_pass = "adminpass"

    async with async_session_test() as session:
        # ensure admin group exists
        q = await session.execute(
            select(UserGroup).where(UserGroup.name == enums.UserGroupEnum.ADMIN.value)
        )  # type: ignore
        grp = q.scalars().first()
        if not grp:
            grp = UserGroup(name=enums.UserGroupEnum.ADMIN.value)
            session.add(grp)
            await session.commit()
            await session.refresh(grp)

        # create admin user
        admin_hashed = get_password_hash(admin_pass)
        admin = User(
            email=admin_email,
            hashed_password=admin_hashed,
            is_active=True,
            group_id=grp.id,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)

    # login as admin to get token
    access, _ = await login_user(client, admin_email, admin_pass)

    # locate target id from DB
    async with async_session_test() as session:
        q = await session.execute(select(User).where(User.email == target_email))  # type: ignore
        target = q.scalars().first()
        assert target is not None
        target_id = target.id

    r = await client.patch(
        f"/api/v1/admin/users/{target_id}/group",
        json={"group": "moderator"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "group_changed"

    # manual activate
    r = await client.patch(
        f"/api/v1/admin/users/{target_id}/activation",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "activated"

    # now target should be able to log in
    await login_user(client, target_email, target_pass)