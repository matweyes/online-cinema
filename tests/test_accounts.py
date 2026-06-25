import pytest
from httpx import AsyncClient

from tests.conftest import activate_user, login_user, register_user


@pytest.mark.asyncio
async def test_register_activate_login_refresh_logout_flow(client: AsyncClient):
    email = "user1@example.com"
    password = "Strongpass_1"

    token = await register_user(client, email, password)

    # login should fail while inactive
    r = await client.post(
        "/api/v1/accounts/login", json={"username": email, "password": password}
    )
    assert r.status_code == 403

    # activate
    await activate_user(client, token)

    access, refresh = await login_user(client, email, password)

    # get /me
    r = await client.get(
        "/api/v1/accounts/me", headers={"Authorization": f"Bearer {access}"}
    )
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
    password = "Strongpass_1"
    token1 = await register_user(client, email, password)

    r = await client.post("/api/v1/accounts/activation/resend", json={"email": email})
    assert r.status_code == 200
    token2 = r.json().get("activation_token")
    assert token2 and token2 != token1

    # activate with new token
    await activate_user(client, token2)


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient):
    email = "user3@example.com"
    old = "Oldpass_1"
    new = "Newpass_123"
    token = await register_user(client, email, old)
    await activate_user(client, token)

    access, _ = await login_user(client, email, old)

    r = await client.patch(
        "/api/v1/accounts/change-password",
        json={"old_password": old, "new_password": new},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "password_changed"

    # old password should not work
    r = await client.post(
        "/api/v1/accounts/login", json={"username": email, "password": old}
    )
    assert r.status_code == 401

    # login with new
    await login_user(client, email, new)


@pytest.mark.asyncio
async def test_forgot_and_reset_password(client: AsyncClient):
    email = "user4@example.com"
    password = "Initialpass_1"
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
    password = "Profilepass_1"
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
