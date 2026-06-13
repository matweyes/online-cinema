import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.accounts import enums
from src.accounts.models import User, UserGroup
from src.accounts.routers import get_password_hash

from tests.conftest import async_session_test


async def register_user(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/api/v1/accounts/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    return resp.json()["activation_token"]


async def activate_user(client: AsyncClient, token: str):
    resp = await client.post("/api/v1/accounts/activate", json={"token": token})
    assert resp.status_code == 200
    assert resp.json().get("status") == "activated"


async def login_user(client: AsyncClient, email: str, password: str):
    resp = await client.post("/api/v1/accounts/login", json={"username": email, "password": password})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data and "refresh_token" in data
    return data["access_token"], data["refresh_token"]


@pytest.mark.asyncio
async def test_register_activate_login_refresh_logout_flow(client: AsyncClient):
    email = "user1@example.com"
    password = "strongpass"

    token = await register_user(client, email, password)

    # login should fail while inactive
    r = await client.post("/api/v1/accounts/login", json={"username": email, "password": password})
    assert r.status_code == 403

    # activate
    await activate_user(client, token)

    access, refresh = await login_user(client, email, password)

    # get /me
    r = await client.get("/api/v1/accounts/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
    assert r.json()["email"] == email

    # refresh
    r = await client.post("/api/v1/accounts/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert "access_token" in r.json()

    # logout (delete refresh token)
    r = await client.post(
        "/api/v1/accounts/logout",
        json={"refresh_token": refresh},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "logged_out"

    # refresh with same token should fail
    r = await client.post("/api/v1/accounts/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_resend_activation(client: AsyncClient):
    email = "user2@example.com"
    password = "strongpass"
    token1 = await register_user(client, email, password)

    r = await client.post("/api/v1/accounts/resend-activation", json={"email": email})
    assert r.status_code == 200
    token2 = r.json().get("activation_token")
    assert token2 and token2 != token1

    # activate with new token
    await activate_user(client, token2)


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient):
    email = "user3@example.com"
    old = "oldpass"
    new = "newpass123"
    token = await register_user(client, email, old)
    await activate_user(client, token)

    access, _ = await login_user(client, email, old)

    r = await client.post(
        "/api/v1/accounts/change-password",
        json={"old_password": old, "new_password": new},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "password_changed"

    # old password should not work
    r = await client.post("/api/v1/accounts/login", json={"username": email, "password": old})
    assert r.status_code == 401

    # login with new
    await login_user(client, email, new)


@pytest.mark.asyncio
async def test_forgot_and_reset_password(client: AsyncClient):
    email = "user4@example.com"
    password = "initialpass"
    new_pass = "resetpass123"
    token = await register_user(client, email, password)
    await activate_user(client, token)

    r = await client.post("/api/v1/accounts/forgot-password", json={"email": email})
    assert r.status_code == 200
    reset_token = r.json().get("reset_token")
    assert reset_token

    r = await client.post(
        "/api/v1/accounts/reset-password",
        json={"token": reset_token, "new_password": new_pass},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "password_reset"

    # login with new password
    await login_user(client, email, new_pass)


@pytest.mark.asyncio
async def test_profile_update(client: AsyncClient):
    email = "user5@example.com"
    password = "profilepass"
    token = await register_user(client, email, password)
    await activate_user(client, token)
    access, _ = await login_user(client, email, password)

    r = await client.patch(
        "/api/v1/accounts/me/profile",
        json={"first_name": "John", "last_name": "Doe", "info": "Loves cinema"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "profile_updated"


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
        q = await session.execute(select(UserGroup).where(UserGroup.name == enums.UserGroupEnum.ADMIN.value))  # type: ignore
        grp = q.scalars().first()
        if not grp:
            grp = UserGroup(name=enums.UserGroupEnum.ADMIN.value)
            session.add(grp)
            await session.commit()
            await session.refresh(grp)

        # create admin user
        admin_hashed = get_password_hash(admin_pass)
        admin = User(email=admin_email, hashed_password=admin_hashed, is_active=True, group_id=grp.id)
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        admin_id = admin.id

    # login as admin to get token
    access, _ = await login_user(client, admin_email, admin_pass)

    # locate target id from DB
    async with async_session_test() as session:
        q = await session.execute(select(User).where(User.email == target_email))  # type: ignore
        target = q.scalars().first()
        assert target is not None
        target_id = target.id

    r = await client.patch(
        f"/api/v1/accounts/users/{target_id}/group",
        json={"group": "moderator"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "group_changed"

    # manual activate
    r = await client.patch(
        f"/api/v1/accounts/users/{target_id}/activate",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "activated"

    # now target should be able to login
    await login_user(client, target_email, target_pass)
