"""
Background scheduler for auto-posting to Instagram.
"""

import asyncio
import os
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_maker, init_db
from app.models import ScheduledPost, AutoPostSettings, Post
from app.services.instagram_poster import post_carousel_to_instagram, post_single_image_to_instagram
from app.services.content_generator import generate_carousel_content
from app.services.image_renderer import get_renderer
from app.services.news_service import search_news_serpapi, generate_hook_headline, generate_ai_news_caption, select_most_viral_topic
from app.services.news_renderer import render_news_post
from app.design_templates import list_color_themes, list_textures, list_layouts
from app.templates import get_all_templates
from app.config import get_settings
import random

settings = get_settings()
scheduler = AsyncIOScheduler()

# Base URL for images - use environment variable or default
BASE_URL = os.environ.get("PUBLIC_URL", "https://instagramposting-production-4e91.up.railway.app")


async def check_and_post_scheduled():
    """Check for scheduled posts that are due and post them. Auto-generates queue if needed."""
    print(f"[Scheduler] Checking at {datetime.now(timezone.utc)}")
    
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
            
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            
            # Check if we have any pending posts for today
            result = await db.execute(
                select(ScheduledPost)
                .where(and_(
                    ScheduledPost.status == "pending",
                    ScheduledPost.scheduled_time >= today_start,
                    ScheduledPost.scheduled_time < today_end
                ))
            )
            today_pending = result.scalars().all()
            
            # Auto-generate queue if no pending posts for today
            if not today_pending:
                print("[Scheduler] No pending posts for today - auto-generating queue")
                await auto_generate_daily_queue(db, auto_settings)
            
            # Find pending posts that are due NOW
            result = await db.execute(
                select(ScheduledPost)
                .where(and_(
                    ScheduledPost.status == "pending",
                    ScheduledPost.scheduled_time <= now
                ))
                .order_by(ScheduledPost.scheduled_time)
                .limit(3)  # Process up to 3 at a time to avoid rate limits
            )
            due_posts = result.scalars().all()
            
            if not due_posts:
                print("[Scheduler] No posts due right now")
                return
            
            print(f"[Scheduler] Found {len(due_posts)} posts to process")
            
            for scheduled in due_posts:
                await process_scheduled_post(db, scheduled, auto_settings)
                # Small delay between posts to avoid rate limiting
                await asyncio.sleep(5)
                
        except Exception as e:
            print(f"[Scheduler] Error: {e}")
            import traceback
            traceback.print_exc()


async def auto_generate_daily_queue(db: AsyncSession, auto_settings: AutoPostSettings):
    """Automatically generate today's posting queue based on settings."""
    # Get post counts
    carousel_count = getattr(auto_settings, 'carousel_count', 2) or 2
    news_count = getattr(auto_settings, 'news_count', 1) or 1
    total_posts = carousel_count + news_count
    
    if total_posts == 0:
        print("[Scheduler] No posts configured - carousel_count and news_count both 0")
        return
    
    # Calculate time distribution
    equal_distribution = getattr(auto_settings, 'equal_distribution', True)
    interval_hours = 24 / total_posts
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Build a list of post types to create
    post_types = ["carousel"] * carousel_count + ["news"] * news_count
    if equal_distribution:
        random.shuffle(post_types)  # Mix them up for variety
    
    created_count = 0
    
    for i, post_type in enumerate(post_types):
        # Calculate scheduled time - spread throughout the day
        scheduled_time = today_start + timedelta(hours=interval_hours * i + interval_hours / 2)
        
        # Skip if the time has already passed (more than 30 min ago)
        if scheduled_time < now - timedelta(minutes=30):
            continue
        
        if post_type == "carousel":
            # Carousel post settings
            template_id = auto_settings.default_template_id or "random"
            color_theme = auto_settings.default_color_theme or "random"
            texture = auto_settings.default_texture or "random"
            layout = auto_settings.default_layout or "random"
            
            # Handle random slide count (0 or None means random)
            slide_count = auto_settings.default_slide_count
            if not slide_count or slide_count == 0:
                slide_count = random.randint(4, 10)
            
            scheduled_post = ScheduledPost(
                scheduled_time=scheduled_time,
                status="pending",
                post_type="carousel",
                template_id=template_id,
                color_theme=color_theme,
                texture=texture,
                layout=layout,
                slide_count=slide_count
            )
        else:
            # News post settings - handle random color
            news_accent = getattr(auto_settings, 'news_accent_color', 'cyan') or 'cyan'
            if news_accent == 'random':
                news_accent = random.choice(['cyan', 'blue', 'green', 'orange', 'red', 'yellow', 'pink', 'purple'])
            
            news_time = getattr(auto_settings, 'news_time_range', '1d') or '1d'
            news_auto = getattr(auto_settings, 'news_auto_select', True)
            if news_auto is None:
                news_auto = True
            
            scheduled_post = ScheduledPost(
                scheduled_time=scheduled_time,
                status="pending",
                post_type="news",
                news_accent_color=news_accent,
                news_time_range=news_time,
                news_auto_select=news_auto
            )
        
        db.add(scheduled_post)
        created_count += 1
    
    await db.commit()
    print(f"[Scheduler] Auto-generated {created_count} posts for today")


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
        
        # Check post type
        is_news = post.metadata_json and post.metadata_json.get("post_type") == "news"
        
        if is_news:
            # News post - single image
            if not post.slide_1_image:
                scheduled.status = "failed"
                scheduled.error_message = "No image for news post"
                await db.commit()
                return
            
            image_path = f"backend/generated_images/{post.slide_1_image}"
            
            print(f"[Scheduler] Posting news to Instagram...")
            result = await post_single_image_to_instagram(
                image_path=image_path,
                caption=post.caption,
                hashtags=post.hashtags,
                base_url=BASE_URL,
                access_token=settings.instagram_access_token
            )
        else:
            # Carousel post - collect all image paths
            image_paths = []
            for img in [post.slide_1_image, post.slide_2_image, post.slide_3_image, post.slide_4_image]:
                if img:
                    image_paths.append(f"backend/generated_images/{img}")
            
            # Add extra slides from metadata (slides 5+)
            if post.metadata_json and "extra_images" in post.metadata_json:
                extra_images = post.metadata_json["extra_images"]
                slide_count = post.metadata_json.get("slide_count", 4)
                for i in range(5, slide_count + 1):
                    img_key = f"slide_{i}_image"
                    if img_key in extra_images and extra_images[img_key]:
                        image_paths.append(f"backend/generated_images/{extra_images[img_key]}")
            
            if len(image_paths) < 2:
                scheduled.status = "failed"
                scheduled.error_message = "Not enough images for carousel"
                await db.commit()
                return
            
            # Post to Instagram
            print(f"[Scheduler] Posting carousel to Instagram...")
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
    
    # Check post type
    post_type = getattr(scheduled, 'post_type', 'carousel') or 'carousel'
    
    if post_type == "news":
        return await generate_news_post_for_schedule(db, scheduled, auto_settings)
    else:
        return await generate_carousel_post_for_schedule(db, scheduled, auto_settings)


async def generate_news_post_for_schedule(db: AsyncSession, scheduled: ScheduledPost, auto_settings: AutoPostSettings) -> Post:
    """Generate a news post for a scheduled item."""
    print(f"[Scheduler] Generating news post for scheduled {scheduled.id}")
    
    # Get news settings
    accent_color = getattr(scheduled, 'news_accent_color', None) or getattr(auto_settings, 'news_accent_color', 'cyan') or 'cyan'
    
    # Handle random color
    if accent_color == 'random':
        accent_color = random.choice(['cyan', 'blue', 'green', 'orange', 'red', 'yellow', 'pink', 'purple'])
    
    time_range = getattr(scheduled, 'news_time_range', None) or getattr(auto_settings, 'news_time_range', '1d') or '1d'
    auto_select = getattr(scheduled, 'news_auto_select', None)
    if auto_select is None:
        auto_select = getattr(auto_settings, 'news_auto_select', True)
    
    # Fetch news
    news = await search_news_serpapi(time_range=time_range)
    if not news:
        print("[Scheduler] No news found")
        return None
    
    # Select news item
    if auto_select:
        news_item = await select_most_viral_topic(news)
    else:
        news_item = news[0]
    
    # Generate headline
    headline = await generate_hook_headline(news_item["title"], news_item.get("snippet", ""))
    category = news_item.get("category", "SUPPLY CHAIN")
    
    # Generate caption
    caption = await generate_ai_news_caption(news_item)
    
    # Map accent color
    accent_colors = {
        "cyan": (0, 200, 255),
        "blue": (59, 130, 246),
        "green": (34, 197, 94),
        "orange": (249, 115, 22),
        "red": (239, 68, 68),
        "yellow": (234, 179, 8),
        "pink": (236, 72, 153),
        "purple": (168, 85, 247),
    }
    accent_rgb = accent_colors.get(accent_color, (0, 200, 255))
    
    # Render image
    image_path = await render_news_post(
        headline=headline,
        category=category,
        accent_color=accent_rgb,
    )
    
    import os
    image_filename = os.path.basename(image_path)
    
    # Create post record
    post = Post(
        topic=headline,
        template_id="news_post",
        slide_1_text=headline,
        slide_2_text="",
        slide_3_text="",
        slide_4_text="",
        caption=caption,
        hashtags="#supplychain #logistics #news #freight #shipping",
        slide_1_image=image_filename,
        slide_2_image=None,
        slide_3_image=None,
        slide_4_image=None,
        metadata_json={
            "post_type": "news",
            "category": category,
            "auto_generated": True,
            "news_item": news_item
        }
    )
    
    db.add(post)
    await db.commit()
    await db.refresh(post)
    
    return post


async def generate_carousel_post_for_schedule(db: AsyncSession, scheduled: ScheduledPost, auto_settings: AutoPostSettings) -> Post:
    """Generate a carousel post for a scheduled item."""
    
    # Get settings - use scheduled overrides or defaults
    template_id = scheduled.template_id or auto_settings.default_template_id or "problem_first"
    color_theme = scheduled.color_theme or auto_settings.default_color_theme or "black"
    texture = scheduled.texture or auto_settings.default_texture or "marble"
    layout = scheduled.layout or auto_settings.default_layout or "centered"
    slide_count = scheduled.slide_count or auto_settings.default_slide_count
    
    # Handle random slide count
    if not slide_count or slide_count == 0:
        slide_count = random.randint(4, 10)
    
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
    renderer = get_renderer(
        color_id=color_theme,
        texture_id=texture,
        layout_id=layout
    )
    
    # Build slide texts list (use _text keys which have formatted strings)
    slide_texts = []
    for i in range(1, slide_count + 1):
        # Try _text key first, fall back to raw key
        text = content.get(f"slide_{i}_text") or content.get(f"slide_{i}", "")
        if isinstance(text, dict):
            text = str(text)  # Convert dict to string if needed
        slide_texts.append(text)
    
    image_paths_list = renderer.render_all_slides(slide_texts)
    
    # Convert to dict
    images = {}
    for i, path in enumerate(image_paths_list, 1):
        images[f"slide_{i}"] = path
    
    # Build metadata with extra slides
    metadata = {
        "color_theme": color_theme,
        "texture": texture,
        "layout": layout,
        "slide_count": slide_count,
        "auto_generated": True
    }
    
    # Add extra slide images to metadata
    for i in range(5, slide_count + 1):
        if f"slide_{i}" in images:
            metadata[f"slide_{i}_image"] = images[f"slide_{i}"]
    
    # Create post record (use _text keys for formatted content)
    post = Post(
        topic=topic,
        template_id=template_id,
        slide_1_text=content.get("slide_1_text", content.get("slide_1", "")),
        slide_2_text=content.get("slide_2_text", content.get("slide_2", "")),
        slide_3_text=content.get("slide_3_text", content.get("slide_3", "")),
        slide_4_text=content.get("slide_4_text", content.get("slide_4", "")),
        caption=content.get("caption_formatted", content.get("caption", "")),
        hashtags=content.get("hashtags_text", content.get("hashtags", "")),
        slide_1_image=images.get("slide_1"),
        slide_2_image=images.get("slide_2"),
        slide_3_image=images.get("slide_3"),
        slide_4_image=images.get("slide_4"),
        metadata_json=metadata
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
    
    # Also run immediately on startup to check if anything is due
    scheduler.add_job(
        check_and_post_scheduled,
        'date',  # Run once immediately
        id="startup_check",
        replace_existing=True,
    )
    
    scheduler.start()
    print("[Scheduler] Started - checking every 2 minutes (initial check scheduled)")


async def trigger_manual_check():
    """Manually trigger a scheduler check (for debugging)."""
    print("[Scheduler] Manual check triggered")
    await check_and_post_scheduled()


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        print("[Scheduler] Stopped")
