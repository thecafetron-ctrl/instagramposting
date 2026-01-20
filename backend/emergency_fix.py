# Emergency: Disable auto-posting and clear scheduled posts
import asyncio
from sqlalchemy import text
from app.database import get_engine

async def emergency_disable():
    engine = get_engine()
    if engine:
        async with engine.begin() as conn:
            # Disable auto-posting
            await conn.execute(text("UPDATE auto_post_settings SET enabled = FALSE"))
            # Cancel all pending posts
            await conn.execute(text("UPDATE scheduled_posts SET status = 'cancelled' WHERE status = 'pending'"))
            print("DONE: Auto-posting disabled, pending posts cancelled")

asyncio.run(emergency_disable())
