from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = get_settings().asyncpg_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set — add it to your environment variables.")
    return create_async_engine(url, echo=False, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
