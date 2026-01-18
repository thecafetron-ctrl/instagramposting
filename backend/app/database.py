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
        try:
            # For asyncpg with Neon, SSL is handled via the URL parameter
            _engine = create_async_engine(
                settings.database_url,
                echo=True,
                pool_pre_ping=True,
                pool_size=3,
                max_overflow=5,
            )
            print(f"✓ Database engine created for: {settings.database_url[:50]}...")
        except Exception as e:
            print(f"✗ Failed to create engine: {e}")
            import traceback
            traceback.print_exc()
            _engine = None
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
        return True
    
    engine = get_engine()
    if not engine:
        print("✗ No database engine available")
        return False
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _initialized = True
        print("✓ Database tables created successfully")
        return True
    except Exception as e:
        print(f"✗ Database init failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def get_db():
    """Dependency for getting database session."""
    if not _initialized:
        success = await init_db()
        if not success:
            raise Exception("Database initialization failed")
    
    session_maker = get_session_maker()
    if session_maker is None:
        raise Exception("Database not configured")
    
    async with session_maker() as session:
        yield session
