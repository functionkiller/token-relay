import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import Base, get_engine, init_db
from app.main import app
from app.models.user import User, UserRole

TEST_DB = "sqlite+aiosqlite:///./test.db"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = get_engine(TEST_DB)
    await init_db(engine)

    # Create admin user
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        result = await s.execute(select(User).where(User.role == UserRole.ADMIN).limit(1))
        if result.scalar_one_or_none() is None:
            s.add(User(
                email="admin@tokenrelay.com",
                hashed_password=pwd_context.hash("admin123456"),
                role=UserRole.ADMIN,
                credit_balance=0,
            ))
            await s.commit()

    yield engine
    await engine.dispose()
    if os.path.exists("test.db"):
        os.remove("test.db")


@pytest_asyncio.fixture
async def db(test_engine):
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    from app.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
