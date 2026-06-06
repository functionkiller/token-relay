from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


def get_engine(database_url: str | None = None):
    url = database_url or settings.DATABASE_URL
    return create_async_engine(url, echo=settings.DEBUG)


def get_session_factory(database_url: str | None = None):
    engine = get_engine(database_url)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


engine = get_engine()
async_session = get_session_factory()


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db(engine_override=None):
    eng = engine_override or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
