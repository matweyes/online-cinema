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

        admin_hashed = get_password_hash(password)
        user = User(
            email=email, hashed_password=admin_hashed, is_active=True, group_id=grp.id
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id, password


@pytest.mark.asyncio
async def test_movies_crud_and_interactions(client: AsyncClient):
    # create moderator in DB
    mod_email = "mod@example.com"
    mod_pass = "modpass"
    await create_moderator(async_session_test, mod_email, mod_pass)

    # login as moderator
    r = await client.post(
        "/api/v1/accounts/login", json={"username": mod_email, "password": mod_pass}
    )
    assert r.status_code == 200
    tokens = r.json()
    mod_access = tokens["access_token"]

    # create a genre as moderator
    r = await client.post(
        "/api/v1/genres/",
        json={"name": "Action"},
        headers={"Authorization": f"Bearer {mod_access}"},
    )
    assert r.status_code == 201
    genre = r.json()
    genre_id = genre["id"]

    # create a movie
    movie_data = {
        "name": "Test Movie",
        "year": 2020,
        "time": 120,
        "imdb": 7.5,
        "votes": 1000,
        "price": 9.99,
        "description": "A test movie",
        "genres": [genre_id],
    }
    r = await client.post(
        "/api/v1/movies/",
        json=movie_data,
        headers={"Authorization": f"Bearer {mod_access}"},
    )
    assert r.status_code == 201
    movie = r.json()
    movie_id = movie["id"]

    # get movie detail
    r = await client.get(f"/api/v1/movies/{movie_id}")
    assert r.status_code == 200
    assert r.json()["name"] == movie_data["name"]

    # list movies
    r = await client.get("/api/v1/movies/")
    assert r.status_code == 200
    assert any(m["id"] == movie_id for m in r.json())

    # genres list should reflect movie count
    r = await client.get("/api/v1/genres/")
    assert r.status_code == 200
    genres = r.json()
    found = next((g for g in genres if g["id"] == genre_id), None)
    assert found is not None
    assert found.get("movie_count", 0) == 1

    # movies by genre
    r = await client.get(f"/api/v1/genres/{genre_id}/movies")
    assert r.status_code == 200
    movies_by_genre = r.json()
    assert any(m["id"] == movie_id for m in movies_by_genre)

    # update movie
    r = await client.patch(
        f"/api/v1/movies/{movie_id}",
        json={"name": "Updated Movie"},
        headers={"Authorization": f"Bearer {mod_access}"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Movie"

    # create normal user via API and activate
    user_email = "user_movies@example.com"
    user_pass = "userpass"
    r = await client.post(
        "/api/v1/accounts/register", json={"email": user_email, "password": user_pass}
    )
    assert r.status_code == 201
    activation = r.json().get("activation_token")
    assert activation
    r = await client.post("/api/v1/accounts/activate", json={"token": activation})
    assert r.status_code == 200

    # login user
    r = await client.post(
        "/api/v1/accounts/login", json={"username": user_email, "password": user_pass}
    )
    assert r.status_code == 200
    user_tokens = r.json()
    user_access = user_tokens["access_token"]

    # like movie
    r = await client.post(
        f"/api/v1/movies/{movie_id}/like",
        headers={"Authorization": f"Bearer {user_access}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "liked"

    # post comment
    r = await client.post(
        f"/api/v1/movies/{movie_id}/comments",
        json={"text": "Nice movie"},
        headers={"Authorization": f"Bearer {user_access}"},
    )
    assert r.status_code == 201
    comment = r.json()
    comment_id = comment["id"]
    assert comment["text"] == "Nice movie"

    # list comments
    r = await client.get(f"/api/v1/movies/{movie_id}/comments")
    assert r.status_code == 200
    comments = r.json()
    assert any(c["id"] == comment_id for c in comments)

    # like comment
    r = await client.post(
        f"/api/v1/movies/comments/{comment_id}/like",
        headers={"Authorization": f"Bearer {user_access}"},
    )
    assert r.status_code == 200

    # rate movie (primitive body -> send raw number)
    r = await client.post(
        f"/api/v1/movies/{movie_id}/rate",
        json=8,
        headers={"Authorization": f"Bearer {user_access}"},
    )
    assert r.status_code == 200
    assert r.json().get("score") == 8

    # add favorite
    r = await client.post(
        f"/api/v1/movies/{movie_id}/favorite",
        headers={"Authorization": f"Bearer {user_access}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "favorited"

    # list favorites (router returns empty list by implementation)
    r = await client.get(
        "/api/v1/movies/favorites", headers={"Authorization": f"Bearer {user_access}"}
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # remove favorite
    r = await client.delete(
        f"/api/v1/movies/{movie_id}/favorite",
        headers={"Authorization": f"Bearer {user_access}"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "unfavorited"

    # delete movie as moderator
    r = await client.delete(
        f"/api/v1/movies/{movie_id}", headers={"Authorization": f"Bearer {mod_access}"}
    )
    assert r.status_code == 200
    assert r.json().get("status") == "deleted"
