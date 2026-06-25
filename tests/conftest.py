import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.accounts import enums
from src.accounts.helpers import get_password_hash
from src.accounts.models import User, UserGroup
from src.database import Base, get_db
from src.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///./data/test.db"

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_test = async_sessionmaker(
    engine_test, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with async_session_test() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True, scope="session")
async def setup_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def clean_db():
    # Clean all tables before each test
    async with async_session_test() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def register_user(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/accounts/register", json={"email": email, "password": password}
    )
    assert resp.status_code == 201
    return resp.json()["activation_token"]


async def activate_user(client: AsyncClient, token: str):
    resp = await client.post("/api/v1/accounts/activation", json={"token": token})
    assert resp.status_code == 200
    assert resp.json().get("status") == "activated"


async def login_user(client: AsyncClient, email: str, password: str):
    resp = await client.post(
        "/api/v1/accounts/login", json={"username": email, "password": password}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data and "refresh_token" in data
    return data["access_token"], data["refresh_token"]


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
