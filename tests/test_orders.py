from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.movies.models import Movie
from tests.conftest import activate_user, async_session_test, login_user, register_user


@pytest.mark.asyncio
async def test_orders_flow(client: AsyncClient):
    # user who will create orders
    email = "orderuser@example.com"
    password = "Orderpass_1"
    token = await register_user(client, email, password)
    await activate_user(client, token)
    access = await login_user(client, email, password)
    access_token = access[0]

    # create a movie
    async with async_session_test() as session:
        m = Movie(
            uuid=str(uuid4()),
            name="Order Test Movie",
            year=2021,
            time=100,
            imdb=8.1,
            votes=500,
            price=12.50,
        )
        session.add(m)
        await session.commit()
        await session.refresh(m)
        movie_id = m.id

    # add to cart
    r = await client.post(
        "/api/v1/cart/items",
        json={"movie_id": movie_id},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 201

    # create order from cart
    r = await client.post(
        "/api/v1/orders/", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert r.status_code == 201
    order = r.json()
    assert order["items"] and len(order["items"]) == 1
    assert order["total_amount"] == pytest.approx(12.5)
    order_id = order["id"]

    # get my orders
    r = await client.get(
        "/api/v1/orders/", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert r.status_code == 200
    orders = r.json()
    assert any(o["id"] == order_id for o in orders)

    # get order details
    r = await client.get(
        f"/api/v1/orders/{order_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 200
    od = r.json()
    assert od["id"] == order_id

    # cancel order
    r = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "canceled"

    # cancelling again should fail
    r = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 400

    # create another order to pay
    # add movie again
    r = await client.post(
        "/api/v1/cart/items",
        json={"movie_id": movie_id},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 201
    r = await client.post(
        "/api/v1/orders/", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert r.status_code == 201
    order2 = r.json()
    order2_id = order2["id"]

    # pay order
    r = await client.post(
        f"/api/v1/orders/{order2_id}/pay",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "paid"

    # admin all orders
    admin_email = "admin@example.com"
    admin_pass = "Adminpass_1"
    token = await register_user(client, admin_email, admin_pass)
    await activate_user(client, token)
    # promote to admin in DB
    async with async_session_test() as session:
        # create admin group if not exists and set user's group
        from src.accounts.models import User, UserGroup

        q = await session.execute(select(UserGroup).where(UserGroup.name == "admin"))
        ag = q.scalars().first()
        if not ag:
            ag = UserGroup(name="admin")
            session.add(ag)
            await session.commit()
            await session.refresh(ag)
        q = await session.execute(select(User).where(User.email == admin_email))
        au = q.scalars().first()
        assert au
        au.group_id = ag.id
        session.add(au)
        await session.commit()

    admin_access = await login_user(client, admin_email, admin_pass)
    admin_access_token = admin_access[0]
    r = await client.get(
        "/api/v1/orders/admin/all",
        headers={"Authorization": f"Bearer {admin_access_token}"},
    )
    assert r.status_code == 200
    all_orders = r.json()
    assert len(all_orders) > 0
    assert any(o["id"] == order2_id for o in all_orders)
