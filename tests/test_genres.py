import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.accounts import enums
from src.accounts.models import User, UserGroup
from src.accounts.routers import get_password_hash
from tests.conftest import async_session_test


async def create_moderator(
    session_factory, email: str, password: str
) -> tuple[int, str]:
    async with session_factory() as session:
        q = await session.execute(
            select(UserGroup).where(
                UserGroup.name == enums.UserGroupEnum.MODERATOR.value
            )
        )  # type: ignore
        grp = q.scalars().first()
        if not grp:
            grp = UserGroup(name=enums.UserGroupEnum.MODERATOR.value)
            session.add(grp)
            await session.commit()
            await session.refresh(grp)

        hashed = get_password_hash(password)
        user = User(
            email=email, hashed_password=hashed, is_active=True, group_id=grp.id
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id, password


@pytest.mark.asyncio
async def test_genres_crud_and_movies(client: AsyncClient):
    # create moderator
    mod_email = "mod2@example.com"
    mod_pass = "modpass2"
    await create_moderator(async_session_test, mod_email, mod_pass)

    # login
    r = await client.post(
        "/api/v1/accounts/login", json={"username": mod_email, "password": mod_pass}
    )
    assert r.status_code == 200
    tokens = r.json()
    mod_access = tokens["access_token"]

    # create genre
    r = await client.post(
        "/api/v1/genres/",
        json={"name": "Thriller"},
        headers={"Authorization": f"Bearer {mod_access}"},
    )
    assert r.status_code == 201
    genre = r.json()
    genre_id = genre["id"]
    assert genre["name"] == "Thriller"

    # list genres
    r = await client.get("/api/v1/genres/")
    assert r.status_code == 200
    genres = r.json()
    found = next((g for g in genres if g["id"] == genre_id), None)
    assert found is not None
    assert found.get("movie_count", 0) == 0

    # create a movie in that genre
    movie_payload = {
        "name": "Genre Movie",
        "year": 2021,
        "time": 100,
        "imdb": 8.1,
        "votes": 500,
        "price": 5.99,
        "genres": [genre_id],
    }
    r = await client.post(
        "/api/v1/movies/",
        json=movie_payload,
        headers={"Authorization": f"Bearer {mod_access}"},
    )
    assert r.status_code == 201
    movie = r.json()
    movie_id = movie["id"]

    # movies by genre
    r = await client.get(f"/api/v1/genres/{genre_id}/movies")
    assert r.status_code == 200
    movies = r.json()
    assert any(m["id"] == movie_id for m in movies)

    # cannot delete genre while it has movies
    r = await client.delete(
        f"/api/v1/genres/{genre_id}", headers={"Authorization": f"Bearer {mod_access}"}
    )
    assert r.status_code == 400

    # update genre name
    r = await client.patch(
        f"/api/v1/genres/{genre_id}",
        json={"name": "Thriller Updated"},
        headers={"Authorization": f"Bearer {mod_access}"},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["name"] == "Thriller Updated"

    # delete movie then delete genre
    r = await client.delete(
        f"/api/v1/movies/{movie_id}", headers={"Authorization": f"Bearer {mod_access}"}
    )
    assert r.status_code == 200
    r = await client.delete(
        f"/api/v1/genres/{genre_id}", headers={"Authorization": f"Bearer {mod_access}"}
    )
    assert r.status_code == 200
    assert r.json().get("status") == "deleted"
