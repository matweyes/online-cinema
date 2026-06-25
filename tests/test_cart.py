from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.movies.models import Movie
from tests.conftest import activate_user, async_session_test, login_user, register_user


@pytest.mark.asyncio
async def test_cart_flow(client: AsyncClient):
    email = "cartuser@example.com"
    password = "Cartpass_1"
    token = await register_user(client, email, password)
    await activate_user(client, token)
    access = await login_user(client, email, password)
    access_token = access[0]

    # Create a movie in DB
    async with async_session_test() as session:
        m = Movie(
            uuid=str(uuid4()),
            name="Test Movie",
            year=2020,
            time=120,
            imdb=7.5,
            votes=1000,
            price=9.99,
        )
        session.add(m)
        await session.commit()
        await session.refresh(m)
        movie_id = m.id

    # Cart should be empty
    r = await client.get(
        "/api/v1/cart/", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert r.status_code == 200
    assert r.json()["items"] == []

    # Add item
    r = await client.post(
        "/api/v1/cart/items",
        json={"movie_id": movie_id},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 201
    item = r.json()
    assert item["movie_id"] == movie_id

    # Adding same item again should fail
    r = await client.post(
        "/api/v1/cart/items",
        json={"movie_id": movie_id},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 400

    # Get cart now contains the item
    r = await client.get(
        "/api/v1/cart/", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["movie_id"] == movie_id

    # Remove item
    r = await client.delete(
        f"/api/v1/cart/items/{movie_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "deleted"

    # Removing again -> 404
    r = await client.delete(
        f"/api/v1/cart/items/{movie_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 404

    # Add again and clear
    r = await client.post(
        "/api/v1/cart/items",
        json={"movie_id": movie_id},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 201
    r = await client.delete(
        "/api/v1/cart/items", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert r.status_code == 200
    assert r.json().get("status") == "cleared"

    r = await client.get(
        "/api/v1/cart/", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_cannot_add_purchased_movie_to_cart(client: AsyncClient):
    email = "purchaseuser@example.com"
    password = "Purchasepass_1"
    token = await register_user(client, email, password)
    await activate_user(client, token)
    access = await login_user(client, email, password)
    access_token = access[0]

    # Create a movie in DB
    async with async_session_test() as session:
        m = Movie(
            uuid=str(uuid4()),
            name="Purchase Test Movie",
            year=2022,
            time=90,
            imdb=7.0,
            votes=200,
            price=14.99,
        )
        session.add(m)
        await session.commit()
        await session.refresh(m)
        movie_id = m.id

    # Add to cart
    r = await client.post(
        "/api/v1/cart/items",
        json={"movie_id": movie_id},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 201

    # Create order from cart
    r = await client.post(
        "/api/v1/orders/", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert r.status_code == 201
    order_id = r.json()["id"]

    # Pay the order (this should create Purchase records)
    r = await client.post(
        f"/api/v1/orders/{order_id}/pay",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "paid"

    # Now try to add the same movie to cart - should fail
    r = await client.post(
        "/api/v1/cart/items",
        json={"movie_id": movie_id},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert r.status_code == 400
    assert "already purchased" in r.json()["detail"].lower()
