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
    """Initialize database tables and run migrations."""
    global _initialized
    if _initialized:
        return True
    
    engine = get_engine()
    if not engine:
        print("✗ No database engine available")
        return False
    
    try:
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            
            # Run migrations to add missing columns (PostgreSQL)
            migration_queries = [
                # AutoPostSettings new columns
                "ALTER TABLE auto_post_settings ADD COLUMN IF NOT EXISTS carousel_count INTEGER DEFAULT 2;",
                "ALTER TABLE auto_post_settings ADD COLUMN IF NOT EXISTS news_count INTEGER DEFAULT 1;",
                "ALTER TABLE auto_post_settings ADD COLUMN IF NOT EXISTS equal_distribution BOOLEAN DEFAULT TRUE;",
                "ALTER TABLE auto_post_settings ADD COLUMN IF NOT EXISTS news_accent_color VARCHAR(50) DEFAULT 'cyan';",
                "ALTER TABLE auto_post_settings ADD COLUMN IF NOT EXISTS news_time_range VARCHAR(20) DEFAULT '1d';",
                "ALTER TABLE auto_post_settings ADD COLUMN IF NOT EXISTS news_auto_select BOOLEAN DEFAULT TRUE;",
                # ScheduledPost new columns
                "ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS post_type VARCHAR(20) DEFAULT 'carousel';",
                "ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS news_accent_color VARCHAR(50);",
                "ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS news_time_range VARCHAR(20);",
                "ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS news_auto_select BOOLEAN;",
                "ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS instagram_post_id VARCHAR(100);",
                "ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS error_message TEXT;",
                "ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS posted_at TIMESTAMP WITH TIME ZONE;",
            ]
            
            from sqlalchemy import text
            for query in migration_queries:
                try:
                    await conn.execute(text(query))
                except Exception as e:
                    # Ignore errors (column already exists, etc.)
                    pass
            
        _initialized = True
        print("✓ Database tables created and migrated successfully")
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
