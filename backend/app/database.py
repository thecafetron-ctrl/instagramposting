"""
Database configuration for Neon PostgreSQL.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

# Lazy engine initialization
_engine = None
_async_session = None


def get_engine():
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_maker():
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(
            get_engine(), 
            class_=AsyncSession, 
            expire_on_commit=False
        )
    return _async_session


class Base(DeclarativeBase):
    pass


async def init_db():
    """Initialize database tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency for getting database session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session
