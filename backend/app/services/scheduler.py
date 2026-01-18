"""
Background scheduler for auto-posting to Instagram.
"""

import asyncio
import os
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_maker, init_db
from app.models import ScheduledPost, AutoPostSettings, Post
from app.services.instagram_poster import post_carousel_to_instagram
from app.services.content_generator import generate_carousel_content
from app.services.image_renderer import get_renderer
from app.design_templates import list_color_themes, list_textures, list_layouts
from app.templates import get_all_templates
from app.config import get_settings
import random

settings = get_settings()
scheduler = AsyncIOScheduler()

# Base URL for images - use environment variable or default
BASE_URL = os.environ.get("PUBLIC_URL", "https://instagramposting-production-4e91.up.railway.app")


async def check_and_post_scheduled():
    """Check for scheduled posts that are due and post them."""
    print(f"[Scheduler] Checking for scheduled posts at {datetime.now(timezone.utc)}")
    
    session_maker = get_session_maker()
    if not session_maker:
        print("[Scheduler] Database not available")
        return
    
    async with session_maker() as db:
        try:
            # Get auto-post settings
            result = await db.execute(select(AutoPostSettings).limit(1))
            auto_settings = result.scalar_one_or_none()
            
            if not auto_settings or not auto_settings.enabled:
                print("[Scheduler] Auto-posting is disabled")
                return
            
            # Find pending posts that are due
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(ScheduledPost)
                .where(and_(
                    ScheduledPost.status == "pending",
                    ScheduledPost.scheduled_time <= now
                ))
                .order_by(ScheduledPost.scheduled_time)
                .limit(5)  # Process up to 5 at a time
            )
            due_posts = result.scalars().all()
            
            if not due_posts:
                print("[Scheduler] No posts due")
                return
            
            print(f"[Scheduler] Found {len(due_posts)} posts to process")
            
            for scheduled in due_posts:
                await process_scheduled_post(db, scheduled, auto_settings)
                
        except Exception as e:
            print(f"[Scheduler] Error: {e}")
            import traceback
            traceback.print_exc()


async def process_scheduled_post(db: AsyncSession, scheduled: ScheduledPost, auto_settings: AutoPostSettings):
    """Process a single scheduled post."""
    print(f"[Scheduler] Processing scheduled post {scheduled.id}")
    
    try:
        # Check if post already exists
        if scheduled.post_id:
            result = await db.execute(
                select(Post).where(Post.id == scheduled.post_id)
            )
            post = result.scalar_one_or_none()
        else:
            post = None
        
        # Generate post if needed
        if not post:
            print(f"[Scheduler] Generating new post for scheduled {scheduled.id}")
            post = await generate_post_for_schedule(db, scheduled, auto_settings)
            if not post:
                scheduled.status = "failed"
                scheduled.error_message = "Failed to generate post"
                await db.commit()
                return
            
            scheduled.post_id = post.id
        
        # Collect image paths
        image_paths = [
            post.slide_1_image,
            post.slide_2_image,
            post.slide_3_image,
            post.slide_4_image
        ]
        
        # Add extra slides from metadata
        if post.metadata_json:
            for i in range(5, 11):
                img_key = f"slide_{i}_image"
                if img_key in post.metadata_json:
                    image_paths.append(post.metadata_json[img_key])
        
        image_paths = [p for p in image_paths if p]
        
        if len(image_paths) < 2:
            scheduled.status = "failed"
            scheduled.error_message = "Not enough images"
            await db.commit()
            return
        
        # Post to Instagram
        print(f"[Scheduler] Posting to Instagram...")
        result = await post_carousel_to_instagram(
            image_paths=image_paths,
            caption=post.caption,
            hashtags=post.hashtags,
            base_url=BASE_URL,
            access_token=settings.instagram_access_token
        )
        
        if result["status"] == "success":
            scheduled.status = "posted"
            scheduled.instagram_post_id = result.get("instagram_post_id")
            scheduled.posted_at = datetime.now(timezone.utc)
            print(f"[Scheduler] Successfully posted! IG ID: {scheduled.instagram_post_id}")
        else:
            scheduled.status = "failed"
            scheduled.error_message = result.get("message", "Unknown error")
            print(f"[Scheduler] Failed to post: {scheduled.error_message}")
        
        await db.commit()
        
    except Exception as e:
        print(f"[Scheduler] Error processing scheduled post: {e}")
        scheduled.status = "failed"
        scheduled.error_message = str(e)
        await db.commit()


async def generate_post_for_schedule(db: AsyncSession, scheduled: ScheduledPost, auto_settings: AutoPostSettings) -> Post:
    """Generate a new post for a scheduled item."""
    
    # Get settings - use scheduled overrides or defaults
    template_id = scheduled.template_id or auto_settings.default_template_id or "problem_first"
    color_theme = scheduled.color_theme or auto_settings.default_color_theme or "black"
    texture = scheduled.texture or auto_settings.default_texture or "marble"
    layout = scheduled.layout or auto_settings.default_layout or "centered"
    slide_count = scheduled.slide_count or auto_settings.default_slide_count or 4
    
    # Randomize if set to random
    if template_id == "random":
        templates = get_all_templates()
        template_id = random.choice([t["id"] for t in templates])
    
    if color_theme == "random":
        colors = list_color_themes()
        color_theme = random.choice([c["id"] for c in colors])
    
    if texture == "random":
        textures = list_textures()
        texture = random.choice([t["id"] for t in textures])
    
    if layout == "random":
        layouts = list_layouts()
        # 60% chance for centered
        if random.random() < 0.6:
            layout = "centered"
        else:
            layout = random.choice([l["id"] for l in layouts if l["id"] != "centered"])
    
    # Simple topic discovery - just use a generic topic
    topic = f"AI-Powered Logistics Optimization #{random.randint(1000, 9999)}"
    
    content = await generate_carousel_content(
        topic=topic,
        template_id=template_id,
        slide_count=slide_count,
        enrichment=None
    )
    
    if not content:
        return None
    
    # Render images
    renderer = get_renderer()
    images = renderer.render_all_slides(
        content=content,
        color_theme=color_theme,
        texture=texture,
        layout=layout
    )
    
    # Create post record
    post = Post(
        topic=topic,
        template_id=template_id,
        slide_1_text=content.get("slide_1", ""),
        slide_2_text=content.get("slide_2", ""),
        slide_3_text=content.get("slide_3", ""),
        slide_4_text=content.get("slide_4", ""),
        caption=content.get("caption", ""),
        hashtags=content.get("hashtags", ""),
        slide_1_image=images.get("slide_1"),
        slide_2_image=images.get("slide_2"),
        slide_3_image=images.get("slide_3"),
        slide_4_image=images.get("slide_4"),
        metadata_json={
            "color_theme": color_theme,
            "texture": texture,
            "layout": layout,
            "slide_count": slide_count,
            "auto_generated": True
        }
    )
    
    db.add(post)
    await db.commit()
    await db.refresh(post)
    
    return post


def start_scheduler():
    """Start the background scheduler."""
    if scheduler.running:
        print("[Scheduler] Already running")
        return
    
    # Check every 2 minutes
    scheduler.add_job(
        check_and_post_scheduled,
        IntervalTrigger(minutes=2),
        id="auto_post_checker",
        replace_existing=True,
        max_instances=1
    )
    
    scheduler.start()
    print("[Scheduler] Started - checking every 2 minutes")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        print("[Scheduler] Stopped")
