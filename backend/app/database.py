"""
Database configuration for Neon PostgreSQL.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

_engine = None
_session_maker = None
_initialized = False


class Base(DeclarativeBase):
    pass


def get_engine():
    global _engine
    if _engine is None and settings.database_url:
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_maker():
    global _session_maker
    if _session_maker is None:
        engine = get_engine()
        if engine:
            _session_maker = async_sessionmaker(
                engine, 
                class_=AsyncSession, 
                expire_on_commit=False
            )
    return _session_maker


async def init_db():
    """Initialize database tables."""
    global _initialized
    if _initialized:
        return
    engine = get_engine()
    if engine:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _initialized = True


async def get_db():
    """Dependency for getting database session."""
    # Init on first use
    await init_db()
    
    session_maker = get_session_maker()
    if session_maker is None:
        raise Exception("Database not configured - set DATABASE_URL")
    
    async with session_maker() as session:
        yield session
