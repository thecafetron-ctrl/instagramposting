"""
API routes for the Instagram carousel generator.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import os
import random


def weighted_layout_choice(layout_ids: list) -> str:
    """Choose layout with 'centered' (Centered Hero) having 60% probability."""
    if "centered" in layout_ids:
        # 60% chance for centered, 40% split among others
        if random.random() < 0.6:
            return "centered"
        else:
            other_layouts = [l for l in layout_ids if l != "centered"]
            if other_layouts:
                return random.choice(other_layouts)
    return random.choice(layout_ids)

from app.database import get_db
from app.models import Post, UsedTopic, ScheduledPost, AutoPostSettings, Lead
from app.templates import get_all_templates, get_template
from app.design_templates import (
    list_design_templates, get_design_template,
    list_color_themes, list_textures, list_layouts,
    COLOR_THEMES, BACKGROUND_TEXTURES, LAYOUT_STYLES
)
from app.services.topic_discovery import discover_fresh_topic, record_used_topic
from app.services.content_generator import generate_carousel_content
from app.services.image_renderer import get_renderer
from app.services.instagram_poster import post_carousel_to_instagram, post_single_image_to_instagram, verify_access_token
from app.services.news_service import search_news_serpapi, get_latest_news, generate_news_caption, generate_hook_headline, generate_ai_news_caption, select_most_viral_topic
from app.services.news_renderer import render_news_post
from app.config import get_settings

router = APIRouter()
settings = get_settings()


# Request/Response Models

class GenerateRequest(BaseModel):
    template_id: str = "problem_first"  # Content template
    color_theme: str = "black"  # Color theme (black, purple, blue, etc.)
    texture: str = "stars"  # Background texture (stars, marble, logistics, etc.)
    layout: str = "centered_left_text"  # Layout style
    slide_count: int = 4  # Number of slides (4-10)
    topic: Optional[str] = None  # If provided, use this topic instead of discovering
    allow_reuse: bool = False
    render_images: bool = True


class NewsPostRequest(BaseModel):
    """Request for generating a news post."""
    custom_headline: Optional[str] = None  # If provided, use this instead of fetching news
    category: Optional[str] = None  # Category label (auto-detected if not provided)
    accent_words: Optional[List[str]] = None  # Words to highlight
    accent_color: Optional[str] = "cyan"  # Highlight color: cyan, blue, green, orange, red, yellow, pink
    time_range: Optional[str] = "1d"  # News age filter: today, 1d, 3d, 1w, 2w, 4w, anytime
    auto_select: Optional[bool] = False  # Let AI pick most viral topic
    selected_news_index: Optional[int] = None  # If provided, use this news item from the list


class GenerateResponse(BaseModel):
    id: int
    topic: str
    template_id: str
    slide_count: int
    slides: list  # List of {text, image} dicts
    caption: str
    hashtags: str


class PostResponse(BaseModel):
    id: int
    topic: str
    template_id: str
    slide_1_text: str
    slide_2_text: str
    slide_3_text: str
    slide_4_text: str
    caption: str
    hashtags: str
    slide_1_image: Optional[str]
    slide_2_image: Optional[str]
    slide_3_image: Optional[str]
    slide_4_image: Optional[str]
    created_at: str


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    icon: str = "📄"
    preview_style: str = ""


class DesignTemplateResponse(BaseModel):
    id: str
    name: str
    description: str


class SettingsResponse(BaseModel):
    brand_name: str
    deduplication_window: int
    topic_api_url: str
    enrichment_api_url: str


class SettingsUpdate(BaseModel):
    brand_name: Optional[str] = None
    deduplication_window: Optional[int] = None
    topic_api_url: Optional[str] = None
    enrichment_api_url: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str


# Routes

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="2.0.0")


@router.get("/debug")
async def debug_info():
    """Debug endpoint to check configuration."""
    import os
    from app.config import get_settings
    s = get_settings()
    return {
        "database_url_set": bool(s.database_url),
        "database_url_prefix": s.database_url[:30] + "..." if s.database_url else None,
        "openai_key_set": bool(s.openai_api_key),
        "env_database_url": bool(os.environ.get("DATABASE_URL")),
    }


@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates():
    """Get all available content templates."""
    return [TemplateResponse(**t) for t in get_all_templates()]


@router.get("/design-templates", response_model=list[DesignTemplateResponse])
async def list_design_templates_route():
    """Get all available visual design templates (legacy)."""
    return [DesignTemplateResponse(**t) for t in list_design_templates()]


@router.get("/color-themes")
async def get_color_themes():
    """Get all available color themes."""
    return list_color_themes()


@router.get("/textures")
async def get_textures():
    """Get all available background textures."""
    return list_textures()


@router.get("/layouts")
async def get_layouts():
    """Get all available layout styles."""
    return list_layouts()


@router.get("/settings", response_model=SettingsResponse)
async def get_current_settings():
    """Get current application settings."""
    return SettingsResponse(
        brand_name=settings.brand_name,
        deduplication_window=settings.deduplication_window,
        topic_api_url=settings.topic_api_url,
        enrichment_api_url=settings.enrichment_api_url,
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate_post(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a new Instagram carousel post.
    
    - Discovers a fresh topic (or uses provided topic)
    - Generates 4-slide content using the selected content template
    - Renders slide images using the selected design template
    - Stores in database
    """
    # Validate content template
    try:
        template = get_template(request.template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Get topic
    if request.topic:
        topic_data = {
            "topic": request.topic,
            "enrichment": {"source": "user_provided", "context": ""}
        }
    else:
        try:
            topic_data = await discover_fresh_topic(db, allow_reuse=request.allow_reuse)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    topic = topic_data["topic"]
    enrichment = topic_data.get("enrichment")
    
    # Validate slide count
    slide_count = max(4, min(10, request.slide_count))
    
    # Generate content
    try:
        content = await generate_carousel_content(
            topic=topic,
            template_id=request.template_id,
            slide_count=slide_count,
            enrichment=enrichment
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Content generation failed: {str(e)}")
    
    # Build slide texts list
    slide_texts = []
    for i in range(1, slide_count + 1):
        slide_texts.append(content.get(f"slide_{i}_text", f"Slide {i} content"))
    
    # Render images with design template
    image_paths = {}
    
    if request.render_images:
        try:
            renderer = get_renderer(
                color_id=request.color_theme,
                texture_id=request.texture,
                layout_id=request.layout
            )
            paths = renderer.render_all_slides(slide_texts)
            for i, path in enumerate(paths, 1):
                image_paths[f"slide_{i}_image"] = path
        except Exception as e:
            print(f"Image rendering failed: {e}")
            import traceback
            traceback.print_exc()
            # Continue without images
    
    # Build raw content dict for all slides
    raw_content = {}
    for i in range(1, slide_count + 1):
        raw_content[f"slide_{i}"] = content.get(f"slide_{i}", {})
    
    # Create post record (store extra slides in metadata)
    post = Post(
        topic=topic,
        template_id=request.template_id,
        slide_1_text=content.get("slide_1_text", ""),
        slide_2_text=content.get("slide_2_text", ""),
        slide_3_text=content.get("slide_3_text", ""),
        slide_4_text=content.get("slide_4_text", ""),
        caption=content.get("caption_formatted", str(content.get("caption", ""))),
        hashtags=content["hashtags_text"],
        slide_1_image=image_paths.get("slide_1_image"),
        slide_2_image=image_paths.get("slide_2_image"),
        slide_3_image=image_paths.get("slide_3_image"),
        slide_4_image=image_paths.get("slide_4_image"),
        metadata_json={
            "enrichment": enrichment,
            "color_theme": request.color_theme,
            "texture": request.texture,
            "layout": request.layout,
            "slide_count": slide_count,
            "raw_content": raw_content,
            "extra_slides": {
                f"slide_{i}_text": content.get(f"slide_{i}_text", "")
                for i in range(5, slide_count + 1)
            },
            "extra_images": {
                f"slide_{i}_image": image_paths.get(f"slide_{i}_image")
                for i in range(5, slide_count + 1)
            }
        }
    )
    
    db.add(post)
    await db.commit()
    await db.refresh(post)
    
    # Record used topic
    await record_used_topic(db, topic, post.id)
    
    # Build slides list for response
    slides = []
    for i in range(1, slide_count + 1):
        slide_text = content.get(f"slide_{i}_text", "")
        slide_image = image_paths.get(f"slide_{i}_image")
        slides.append({
            "number": i,
            "text": slide_text,
            "image": slide_image
        })
    
    return GenerateResponse(
        id=post.id,
        topic=post.topic,
        template_id=post.template_id,
        slide_count=slide_count,
        slides=slides,
        caption=post.caption,
        hashtags=post.hashtags,
    )


@router.get("/posts", response_model=list[PostResponse])
async def list_posts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get all generated posts."""
    try:
        result = await db.execute(
            select(Post)
            .order_by(desc(Post.created_at))
            .limit(limit)
            .offset(offset)
        )
        posts = result.scalars().all()
    except Exception as e:
        print(f"Database error in posts: {e}")
        return []
    
    return [
        PostResponse(
            id=p.id,
            topic=p.topic,
            template_id=p.template_id,
            slide_1_text=p.slide_1_text,
            slide_2_text=p.slide_2_text,
            slide_3_text=p.slide_3_text,
            slide_4_text=p.slide_4_text,
            caption=p.caption,
            hashtags=p.hashtags,
            slide_1_image=p.slide_1_image,
            slide_2_image=p.slide_2_image,
            slide_3_image=p.slide_3_image,
            slide_4_image=p.slide_4_image,
            created_at=p.created_at.isoformat() if p.created_at else "",
        )
        for p in posts
    ]


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific post by ID."""
    result = await db.execute(
        select(Post).where(Post.id == post_id)
    )
    post = result.scalar_one_or_none()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return PostResponse(
        id=post.id,
        topic=post.topic,
        template_id=post.template_id,
        slide_1_text=post.slide_1_text,
        slide_2_text=post.slide_2_text,
        slide_3_text=post.slide_3_text,
        slide_4_text=post.slide_4_text,
        caption=post.caption,
        hashtags=post.hashtags,
        slide_1_image=post.slide_1_image,
        slide_2_image=post.slide_2_image,
        slide_3_image=post.slide_3_image,
        slide_4_image=post.slide_4_image,
        created_at=post.created_at.isoformat() if post.created_at else "",
    )


@router.get("/images/{filename}")
async def get_image(filename: str):
    """Serve generated images."""
    filepath = f"generated_images/{filename}"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(filepath, media_type="image/png")


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a post."""
    result = await db.execute(
        select(Post).where(Post.id == post_id)
    )
    post = result.scalar_one_or_none()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Delete associated images
    for img_path in [post.slide_1_image, post.slide_2_image, post.slide_3_image, post.slide_4_image]:
        if img_path and os.path.exists(img_path):
            try:
                os.remove(img_path)
            except:
                pass
    
    await db.delete(post)
    await db.commit()
    
    return {"status": "deleted", "id": post_id}


@router.get("/topics/used")
async def list_used_topics(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Get recently used topics."""
    result = await db.execute(
        select(UsedTopic)
        .order_by(desc(UsedTopic.created_at))
        .limit(limit)
    )
    topics = result.scalars().all()
    
    return [
        {
            "id": t.id,
            "topic": t.topic,
            "post_id": t.post_id,
            "created_at": t.created_at.isoformat() if t.created_at else "",
        }
        for t in topics
    ]


# ============= SCHEDULING ENDPOINTS =============

class AutoPostSettingsRequest(BaseModel):
    enabled: bool = False
    posts_per_day: int = 3
    # Post type distribution
    carousel_count: int = 2
    news_count: int = 1
    equal_distribution: bool = True
    # Carousel defaults
    default_template_id: Optional[str] = None
    default_color_theme: Optional[str] = None
    default_texture: Optional[str] = None
    default_layout: Optional[str] = None
    default_slide_count: int = 4
    # News defaults
    news_accent_color: str = "cyan"
    news_time_range: str = "1d"
    news_auto_select: bool = True
    # Credentials
    instagram_username: Optional[str] = None
    instagram_password: Optional[str] = None


class AutoPostSettingsResponse(BaseModel):
    id: int
    enabled: bool
    posts_per_day: int
    # Post type distribution
    carousel_count: int = 2
    news_count: int = 1
    equal_distribution: bool = True
    # Carousel defaults
    default_template_id: Optional[str]
    default_color_theme: Optional[str]
    default_texture: Optional[str]
    default_layout: Optional[str]
    default_slide_count: int
    # News defaults
    news_accent_color: str = "cyan"
    news_time_range: str = "1d"
    news_auto_select: bool = True
    # Credentials
    instagram_username: Optional[str]
    has_credentials: bool


class ScheduledPostRequest(BaseModel):
    scheduled_time: Optional[str] = None  # ISO format, None = calculate next slot
    template_id: Optional[str] = None  # None = random/default
    color_theme: Optional[str] = None
    texture: Optional[str] = None
    layout: Optional[str] = None
    slide_count: int = 4
    post_id: Optional[int] = None  # Link to existing post


class ScheduledPostResponse(BaseModel):
    id: int
    post_id: Optional[int]
    scheduled_time: str
    status: str
    post_type: str = "carousel"  # carousel or news
    template_id: Optional[str]
    color_theme: Optional[str]
    texture: Optional[str]
    layout: Optional[str]
    slide_count: int
    # News settings
    news_accent_color: Optional[str] = None
    news_time_range: Optional[str] = None
    news_auto_select: Optional[bool] = None
    instagram_post_id: Optional[str]
    error_message: Optional[str]
    created_at: str


@router.get("/auto-post/settings")
async def get_auto_post_settings(db: AsyncSession = Depends(get_db)):
    """Get auto-posting settings."""
    try:
        result = await db.execute(select(AutoPostSettings).limit(1))
        settings_row = result.scalar_one_or_none()
        
        if not settings_row:
            # Create default settings
            settings_row = AutoPostSettings(
                enabled=False,
                posts_per_day=3,
                carousel_count=2,
                news_count=1,
                equal_distribution=True,
                default_slide_count=4
            )
            db.add(settings_row)
            await db.commit()
            await db.refresh(settings_row)
        
        return AutoPostSettingsResponse(
            id=settings_row.id,
            enabled=settings_row.enabled,
            posts_per_day=settings_row.posts_per_day,
            carousel_count=getattr(settings_row, 'carousel_count', 2) or 2,
            news_count=getattr(settings_row, 'news_count', 1) or 1,
            equal_distribution=getattr(settings_row, 'equal_distribution', True) if getattr(settings_row, 'equal_distribution', None) is not None else True,
            default_template_id=settings_row.default_template_id,
            default_color_theme=settings_row.default_color_theme,
            default_texture=settings_row.default_texture,
            default_layout=settings_row.default_layout,
            default_slide_count=settings_row.default_slide_count,
            news_accent_color=getattr(settings_row, 'news_accent_color', 'cyan') or 'cyan',
            news_time_range=getattr(settings_row, 'news_time_range', '1d') or '1d',
            news_auto_select=getattr(settings_row, 'news_auto_select', True) if getattr(settings_row, 'news_auto_select', None) is not None else True,
            instagram_username=settings_row.instagram_username,
            has_credentials=bool(settings_row.instagram_password)
        )
    except Exception as e:
        print(f"Database error in auto-post/settings: {e}")
        # Return default settings if DB fails
        return AutoPostSettingsResponse(
            id=0,
            enabled=False,
            posts_per_day=3,
            carousel_count=2,
            news_count=1,
            equal_distribution=True,
            default_template_id=None,
            default_color_theme=None,
            default_texture=None,
            default_layout=None,
            default_slide_count=4,
            news_accent_color="cyan",
            news_time_range="1d",
            news_auto_select=True,
            instagram_username=None,
            has_credentials=False
        )


@router.put("/auto-post/settings")
async def update_auto_post_settings(
    request: AutoPostSettingsRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update auto-posting settings."""
    result = await db.execute(select(AutoPostSettings).limit(1))
    settings_row = result.scalar_one_or_none()
    
    if not settings_row:
        settings_row = AutoPostSettings()
        db.add(settings_row)
    
    settings_row.enabled = request.enabled
    settings_row.posts_per_day = request.posts_per_day
    
    # Post type distribution
    settings_row.carousel_count = request.carousel_count
    settings_row.news_count = request.news_count
    settings_row.equal_distribution = request.equal_distribution
    
    # Carousel defaults
    settings_row.default_template_id = request.default_template_id
    settings_row.default_color_theme = request.default_color_theme
    settings_row.default_texture = request.default_texture
    settings_row.default_layout = request.default_layout
    settings_row.default_slide_count = request.default_slide_count
    
    # News defaults
    settings_row.news_accent_color = request.news_accent_color
    settings_row.news_time_range = request.news_time_range
    settings_row.news_auto_select = request.news_auto_select
    
    if request.instagram_username is not None:
        settings_row.instagram_username = request.instagram_username
    if request.instagram_password is not None:
        settings_row.instagram_password = request.instagram_password
    
    await db.commit()
    await db.refresh(settings_row)
    
    return AutoPostSettingsResponse(
        id=settings_row.id,
        enabled=settings_row.enabled,
        posts_per_day=settings_row.posts_per_day,
        carousel_count=settings_row.carousel_count or 2,
        news_count=settings_row.news_count or 1,
        equal_distribution=settings_row.equal_distribution if settings_row.equal_distribution is not None else True,
        default_template_id=settings_row.default_template_id,
        default_color_theme=settings_row.default_color_theme,
        default_texture=settings_row.default_texture,
        default_layout=settings_row.default_layout,
        default_slide_count=settings_row.default_slide_count,
        news_accent_color=settings_row.news_accent_color or "cyan",
        news_time_range=settings_row.news_time_range or "1d",
        news_auto_select=settings_row.news_auto_select if settings_row.news_auto_select is not None else True,
        instagram_username=settings_row.instagram_username,
        has_credentials=bool(settings_row.instagram_password)
    )


@router.get("/scheduled-posts")
async def list_scheduled_posts(
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """List scheduled posts."""
    try:
        query = select(ScheduledPost).order_by(ScheduledPost.scheduled_time)
        
        if status:
            query = query.where(ScheduledPost.status == status)
        
        result = await db.execute(query.limit(limit))
        posts = result.scalars().all()
    except Exception as e:
        print(f"Database error in scheduled-posts: {e}")
        return []
    
    return [
        ScheduledPostResponse(
            id=p.id,
            post_id=p.post_id,
            scheduled_time=p.scheduled_time.isoformat() if p.scheduled_time else "",
            status=p.status,
            post_type=getattr(p, 'post_type', 'carousel') or 'carousel',
            template_id=p.template_id,
            color_theme=p.color_theme,
            texture=p.texture,
            layout=p.layout,
            slide_count=p.slide_count or 4,
            news_accent_color=getattr(p, 'news_accent_color', None),
            news_time_range=getattr(p, 'news_time_range', None),
            news_auto_select=getattr(p, 'news_auto_select', None),
            instagram_post_id=p.instagram_post_id,
            error_message=p.error_message,
            created_at=p.created_at.isoformat() if p.created_at else ""
        )
        for p in posts
    ]


@router.post("/scheduled-posts")
async def create_scheduled_post(
    request: ScheduledPostRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new scheduled post."""
    # Calculate scheduled time if not provided
    if request.scheduled_time:
        scheduled_time = datetime.fromisoformat(request.scheduled_time.replace('Z', '+00:00'))
    else:
        # Find next available slot based on settings
        settings_result = await db.execute(select(AutoPostSettings).limit(1))
        settings_row = settings_result.scalar_one_or_none()
        posts_per_day = settings_row.posts_per_day if settings_row else 3
        
        # Calculate interval between posts
        interval_hours = 24 / posts_per_day
        
        # Get latest scheduled post
        latest_result = await db.execute(
            select(ScheduledPost)
            .where(ScheduledPost.status == "pending")
            .order_by(desc(ScheduledPost.scheduled_time))
            .limit(1)
        )
        latest = latest_result.scalar_one_or_none()
        
        if latest and latest.scheduled_time:
            scheduled_time = latest.scheduled_time + timedelta(hours=interval_hours)
        else:
            # Start from next interval
            now = datetime.utcnow()
            scheduled_time = now + timedelta(hours=interval_hours)
    
    # Create scheduled post
    scheduled_post = ScheduledPost(
        post_id=request.post_id,
        scheduled_time=scheduled_time,
        status="pending",
        template_id=request.template_id,
        color_theme=request.color_theme,
        texture=request.texture,
        layout=request.layout,
        slide_count=request.slide_count
    )
    
    db.add(scheduled_post)
    await db.commit()
    await db.refresh(scheduled_post)
    
    return ScheduledPostResponse(
        id=scheduled_post.id,
        post_id=scheduled_post.post_id,
        scheduled_time=scheduled_post.scheduled_time.isoformat() if scheduled_post.scheduled_time else "",
        status=scheduled_post.status,
        template_id=scheduled_post.template_id,
        color_theme=scheduled_post.color_theme,
        texture=scheduled_post.texture,
        layout=scheduled_post.layout,
        slide_count=scheduled_post.slide_count or 4,
        instagram_post_id=scheduled_post.instagram_post_id,
        error_message=scheduled_post.error_message,
        created_at=scheduled_post.created_at.isoformat() if scheduled_post.created_at else ""
    )


@router.delete("/scheduled-posts/{scheduled_id}")
async def delete_scheduled_post(
    scheduled_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a scheduled post."""
    result = await db.execute(
        select(ScheduledPost).where(ScheduledPost.id == scheduled_id)
    )
    scheduled = result.scalar_one_or_none()
    
    if not scheduled:
        raise HTTPException(status_code=404, detail="Scheduled post not found")
    
    await db.delete(scheduled)
    await db.commit()
    
    return {"status": "deleted", "id": scheduled_id}


@router.post("/scheduled-posts/generate-queue")
async def generate_schedule_queue(
    db: AsyncSession = Depends(get_db)
):
    """Generate the daily queue of scheduled posts based on settings."""
    # Get settings
    settings_result = await db.execute(select(AutoPostSettings).limit(1))
    settings_row = settings_result.scalar_one_or_none()
    
    if not settings_row:
        raise HTTPException(status_code=400, detail="Auto-post settings not configured")
    
    # Get post counts for each type
    carousel_count = settings_row.carousel_count if hasattr(settings_row, 'carousel_count') else settings_row.posts_per_day
    news_count = settings_row.news_count if hasattr(settings_row, 'news_count') else 0
    total_posts = carousel_count + news_count
    
    if total_posts == 0:
        return {"status": "success", "posts_created": 0, "posts": []}
    
    # Calculate time distribution
    equal_distribution = settings_row.equal_distribution if hasattr(settings_row, 'equal_distribution') else True
    interval_hours = 24 / total_posts if equal_distribution else 24 / max(total_posts, 1)
    
    # Clear existing pending posts for today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Get available options for randomization
    templates = get_all_templates()
    template_ids = [t["id"] for t in templates]
    color_theme_ids = list(COLOR_THEMES.keys())
    texture_ids = list(BACKGROUND_TEXTURES.keys())
    layout_ids = list(LAYOUT_STYLES.keys())
    
    created_posts = []
    
    # Build a list of post types to create
    post_types = ["carousel"] * carousel_count + ["news"] * news_count
    if equal_distribution:
        random.shuffle(post_types)  # Mix them up for variety
    
    for i, post_type in enumerate(post_types):
        scheduled_time = today_start + timedelta(hours=interval_hours * i + interval_hours / 2)
        
        if post_type == "carousel":
            # Carousel post settings
            template_id = settings_row.default_template_id or random.choice(template_ids)
            color_theme = settings_row.default_color_theme or random.choice(color_theme_ids)
            texture = settings_row.default_texture or random.choice(texture_ids)
            layout = settings_row.default_layout or weighted_layout_choice(layout_ids)
            slide_count = settings_row.default_slide_count or 4
            
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
            # News post settings
            news_accent = settings_row.news_accent_color if hasattr(settings_row, 'news_accent_color') else "cyan"
            news_time = settings_row.news_time_range if hasattr(settings_row, 'news_time_range') else "1d"
            news_auto = settings_row.news_auto_select if hasattr(settings_row, 'news_auto_select') else True
            
            scheduled_post = ScheduledPost(
                scheduled_time=scheduled_time,
                status="pending",
                post_type="news",
                news_accent_color=news_accent,
                news_time_range=news_time,
                news_auto_select=news_auto
            )
        
        db.add(scheduled_post)
        created_posts.append(scheduled_post)
    
    await db.commit()
    
    # Refresh all
    for p in created_posts:
        await db.refresh(p)
    
    return {
        "status": "success",
        "posts_created": len(created_posts),
        "carousel_count": carousel_count,
        "news_count": news_count,
        "posts": [
            {
                "id": p.id,
                "scheduled_time": p.scheduled_time.isoformat(),
                "post_type": p.post_type if hasattr(p, 'post_type') else "carousel",
                "template_id": p.template_id,
                "color_theme": p.color_theme,
            }
            for p in created_posts
        ]
    }


class PostToInstagramRequest(BaseModel):
    post_id: int
    base_url: Optional[str] = None  # Base URL for serving images (auto-detected if not provided)


@router.post("/instagram/post")
async def post_to_instagram(
    request: PostToInstagramRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Post a generated carousel OR single image to Instagram using the Graph API.
    Automatically detects news posts (single image) vs carousels.
    """
    # Get the post
    result = await db.execute(
        select(Post).where(Post.id == request.post_id)
    )
    post = result.scalar_one_or_none()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Determine base URL for serving images
    import os
    base_url = request.base_url or os.environ.get("PUBLIC_URL", "https://instagramposting-production-4e91.up.railway.app")
    
    # Check if this is a news post (single image)
    is_news_post = post.metadata_json and post.metadata_json.get("post_type") == "news"
    
    if is_news_post:
        # Single image post for news
        if not post.slide_1_image:
            raise HTTPException(status_code=400, detail="No image found for news post")
        
        # Build full path - extract just filename to avoid double paths
        filename = os.path.basename(post.slide_1_image)
        image_path = f"generated_images/{filename}"
        
        ig_result = await post_single_image_to_instagram(
            image_path=image_path,
            caption=post.caption,
            hashtags=post.hashtags,
            base_url=base_url
        )
    else:
        # Carousel post
        # Collect all image paths (slides 1-4)
        image_paths = []
        for img in [post.slide_1_image, post.slide_2_image, post.slide_3_image, post.slide_4_image]:
            if img:
                # Extract just the filename (handle both "generated_images/file.png" and "file.png")
                filename = os.path.basename(img)
                image_paths.append(f"generated_images/{filename}")
        
        # Add any additional slides from metadata (slides 5+)
        if post.metadata_json and "extra_images" in post.metadata_json:
            extra_images = post.metadata_json["extra_images"]
            slide_count = post.metadata_json.get("slide_count", 4)
            for i in range(5, slide_count + 1):
                img_key = f"slide_{i}_image"
                if img_key in extra_images and extra_images[img_key]:
                    filename = os.path.basename(extra_images[img_key])
                    image_paths.append(f"generated_images/{filename}")
        
        if len(image_paths) < 2:
            raise HTTPException(
                status_code=400, 
                detail="Need at least 2 images for a carousel"
            )
        
        ig_result = await post_carousel_to_instagram(
            image_paths=image_paths,
            caption=post.caption,
            hashtags=post.hashtags,
            base_url=base_url
        )
    
    return {
        "post_id": post.id,
        **ig_result
    }


@router.get("/instagram/verify")
async def verify_instagram_connection():
    """Verify the Instagram API connection and get account info."""
    result = await verify_access_token()
    return result


@router.get("/instagram/diagnose/{post_id}")
async def diagnose_instagram_post(
    post_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Diagnose why an Instagram post might fail.
    Checks image accessibility and returns detailed info.
    """
    import httpx
    import os
    
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    
    if not post:
        return {"error": "Post not found"}
    
    base_url = os.environ.get("PUBLIC_URL", "https://instagramposting-production-4e91.up.railway.app")
    
    diagnosis = {
        "post_id": post_id,
        "base_url": base_url,
        "is_news_post": post.metadata_json and post.metadata_json.get("post_type") == "news",
        "images": [],
        "instagram_token_valid": False,
    }
    
    # Check Instagram token
    token_result = await verify_access_token()
    diagnosis["instagram_token_valid"] = token_result.get("status") == "valid"
    diagnosis["instagram_user"] = token_result.get("username")
    
    # Get image list
    if diagnosis["is_news_post"]:
        images = [post.slide_1_image] if post.slide_1_image else []
    else:
        images = [post.slide_1_image, post.slide_2_image, post.slide_3_image, post.slide_4_image]
        images = [img for img in images if img]
        
        # Add extra slides
        if post.metadata_json and "extra_images" in post.metadata_json:
            for i in range(5, 11):
                img_key = f"slide_{i}_image"
                if img_key in post.metadata_json["extra_images"]:
                    images.append(post.metadata_json["extra_images"][img_key])
    
    # Check each image
    async with httpx.AsyncClient(timeout=10.0) as client:
        for img in images:
            # Extract filename to handle paths like "generated_images/file.png"
            filename = os.path.basename(img)
            img_info = {
                "filename": filename,
                "original_value": img,
                "local_path": f"generated_images/{filename}",
                "url": f"{base_url}/images/{filename}",
                "local_exists": False,
                "url_accessible": False,
                "url_status": None,
                "content_type": None,
            }
            
            # Check local file - try multiple paths
            local_path = f"generated_images/{filename}"
            if not os.path.exists(local_path):
                local_path = f"backend/generated_images/{filename}"
            img_info["local_exists"] = os.path.exists(local_path)
            if img_info["local_exists"]:
                img_info["file_size"] = os.path.getsize(local_path)
                img_info["actual_path"] = local_path
            
            # Check URL accessibility
            try:
                response = await client.head(img_info["url"], follow_redirects=True)
                img_info["url_status"] = response.status_code
                img_info["url_accessible"] = response.status_code == 200
                img_info["content_type"] = response.headers.get("content-type")
            except Exception as e:
                img_info["url_error"] = str(e)
            
            diagnosis["images"].append(img_info)
    
    # Summary
    all_accessible = all(img["url_accessible"] for img in diagnosis["images"])
    diagnosis["all_images_accessible"] = all_accessible
    
    if not all_accessible:
        diagnosis["suggestion"] = "Some images are not publicly accessible. Instagram API requires images to be served via HTTPS URLs that Instagram's servers can reach."
    
    return diagnosis


@router.post("/instagram/test")
async def test_instagram_post(
    db: AsyncSession = Depends(get_db)
):
    """
    Test Instagram posting with the most recent post.
    For debugging purposes.
    """
    # Get the most recent post
    result = await db.execute(
        select(Post).order_by(desc(Post.created_at)).limit(1)
    )
    post = result.scalar_one_or_none()
    
    if not post:
        return {"status": "error", "message": "No posts available to test"}
    
    return {
        "status": "ready",
        "message": "Test endpoint - would post this carousel",
        "post_id": post.id,
        "images": [
            post.slide_1_image,
            post.slide_2_image,
            post.slide_3_image,
            post.slide_4_image
        ],
        "caption_preview": post.caption[:200] + "..." if len(post.caption) > 200 else post.caption
    }


# ============================================================================
# NEWS POST ENDPOINTS
# ============================================================================

@router.get("/news/latest")
async def get_news_articles(
    count: int = 5,
    time_range: str = "1d"
):
    """
    Fetch latest supply chain and logistics news articles.
    Returns list of news items that can be used for news posts.
    
    time_range: today, 1d, 3d, 1w, 2w, 4w, anytime
    """
    try:
        news = await search_news_serpapi(time_range=time_range)
        return {
            "status": "success",
            "news": news[:count],
            "count": len(news[:count]),
            "time_range": time_range
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "news": []
        }


@router.post("/news/generate")
async def generate_news_post(
    request: NewsPostRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a news post image.
    Either fetches latest news or uses custom headline.
    """
    try:
        # Get headline - either custom or from news API
        if request.custom_headline:
            # Generate hook headline using AI (only improves if needed)
            headline = await generate_hook_headline(request.custom_headline, "")
            category = request.category or "SUPPLY CHAIN"
            # Create a news item for AI caption generation
            custom_news_item = {
                "title": request.custom_headline,
                "snippet": "",
                "source": "",
                "category": category,
            }
            caption = await generate_ai_news_caption(custom_news_item)
        else:
            # Fetch latest news with time filter
            time_range = request.time_range or "1d"
            news = await search_news_serpapi(time_range=time_range)
            if not news:
                raise HTTPException(status_code=500, detail="Failed to fetch news")
            
            # Select news item
            if request.auto_select:
                # AI picks the most viral topic
                news_item = await select_most_viral_topic(news)
            elif request.selected_news_index is not None and 0 <= request.selected_news_index < len(news):
                # Use user-selected news item
                news_item = news[request.selected_news_index]
            else:
                # Use first news item
                news_item = news[0]
            
            # Generate headline - AI only improves if original is unclear
            headline = await generate_hook_headline(news_item["title"], news_item.get("snippet", ""))
            category = request.category or news_item.get("category", "SUPPLY CHAIN")
            # Generate detailed AI caption with full news info
            caption = await generate_ai_news_caption(news_item)
        
        # Map accent color name to RGB
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
        accent_color = accent_colors.get(request.accent_color or "cyan", (0, 200, 255))
        
        # Render the news post image (async - fetches Unsplash image)
        image_path = await render_news_post(
            headline=headline,
            category=category,
            accent_words=request.accent_words,
            accent_color=accent_color,
        )
        
        # Extract just the filename for the URL
        image_filename = os.path.basename(image_path)
        
        # Save to database
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
            }
        )
        
        db.add(post)
        await db.commit()
        await db.refresh(post)
        
        return {
            "status": "success",
            "post_type": "news",
            "id": post.id,
            "headline": headline,
            "category": category,
            "image": image_filename,
            "caption": caption,
            "created_at": post.created_at.isoformat() if post.created_at else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate news post: {str(e)}")


@router.get("/news/preview")
async def preview_news_post(
    headline: str,
    category: str = "SUPPLY CHAIN",
):
    """
    Preview a news post without saving.
    Just generates the image and returns the path.
    """
    try:
        image_path = await render_news_post(
            headline=headline,
            category=category,
        )
        
        image_filename = os.path.basename(image_path)
        
        return {
            "status": "success",
            "image": image_filename,
            "headline": headline,
            "category": category,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate preview: {str(e)}")


# ============================================================================
# LEAD MANAGEMENT ENDPOINTS
# ============================================================================

class CreateLeadRequest(BaseModel):
    name: str
    instagram_handle: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    status: Optional[str] = "new"
    follow_up_date: Optional[datetime] = None
    source_post_id: Optional[int] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class UpdateLeadRequest(BaseModel):
    name: Optional[str] = None
    instagram_handle: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    status: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    source_post_id: Optional[int] = None
    source: Optional[str] = None
    notes: Optional[str] = None


@router.get("/leads")
async def list_leads(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all leads, optionally filtered by status."""
    query = select(Lead).order_by(desc(Lead.created_at))
    
    if status:
        query = query.where(Lead.status == status)
    
    result = await db.execute(query)
    leads = result.scalars().all()
    
    return [
        {
            "id": lead.id,
            "name": lead.name,
            "instagram_handle": lead.instagram_handle,
            "email": lead.email,
            "phone": lead.phone,
            "company": lead.company,
            "status": lead.status,
            "follow_up_date": lead.follow_up_date.isoformat() if lead.follow_up_date else None,
            "source_post_id": lead.source_post_id,
            "source": lead.source,
            "notes": lead.notes,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
        }
        for lead in leads
    ]


@router.get("/leads/statuses")
async def get_lead_statuses():
    """Get available lead statuses."""
    return [
        {"id": "new", "label": "New", "color": "#6c757d"},
        {"id": "no_answer", "label": "No Answer", "color": "#ffc107"},
        {"id": "follow_up", "label": "Follow Up", "color": "#17a2b8"},
        {"id": "booked", "label": "Booked", "color": "#28a745"},
        {"id": "closed", "label": "Closed (Won)", "color": "#007bff"},
        {"id": "lost", "label": "Lost", "color": "#dc3545"},
    ]


@router.post("/leads")
async def create_lead(
    request: CreateLeadRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new lead."""
    lead = Lead(
        name=request.name,
        instagram_handle=request.instagram_handle,
        email=request.email,
        phone=request.phone,
        company=request.company,
        status=request.status or "new",
        follow_up_date=request.follow_up_date,
        source_post_id=request.source_post_id,
        source=request.source,
        notes=request.notes,
    )
    
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    
    return {
        "id": lead.id,
        "name": lead.name,
        "status": lead.status,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
    }


@router.get("/leads/{lead_id}")
async def get_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return {
        "id": lead.id,
        "name": lead.name,
        "instagram_handle": lead.instagram_handle,
        "email": lead.email,
        "phone": lead.phone,
        "company": lead.company,
        "status": lead.status,
        "follow_up_date": lead.follow_up_date.isoformat() if lead.follow_up_date else None,
        "source_post_id": lead.source_post_id,
        "source": lead.source,
        "notes": lead.notes,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


@router.put("/leads/{lead_id}")
async def update_lead(
    lead_id: int,
    request: UpdateLeadRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Update fields if provided
    if request.name is not None:
        lead.name = request.name
    if request.instagram_handle is not None:
        lead.instagram_handle = request.instagram_handle
    if request.email is not None:
        lead.email = request.email
    if request.phone is not None:
        lead.phone = request.phone
    if request.company is not None:
        lead.company = request.company
    if request.status is not None:
        lead.status = request.status
    if request.follow_up_date is not None:
        lead.follow_up_date = request.follow_up_date
    if request.source_post_id is not None:
        lead.source_post_id = request.source_post_id
    if request.source is not None:
        lead.source = request.source
    if request.notes is not None:
        lead.notes = request.notes
    
    await db.commit()
    await db.refresh(lead)
    
    return {
        "id": lead.id,
        "name": lead.name,
        "status": lead.status,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


@router.delete("/leads/{lead_id}")
async def delete_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    await db.delete(lead)
    await db.commit()
    
    return {"status": "deleted", "id": lead_id}


@router.patch("/leads/{lead_id}/status")
async def update_lead_status(
    lead_id: int,
    status: str,
    follow_up_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """Quick update just the status of a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    lead.status = status
    if follow_up_date:
        lead.follow_up_date = follow_up_date
    
    await db.commit()
    await db.refresh(lead)
    
    return {
        "id": lead.id,
        "status": lead.status,
        "follow_up_date": lead.follow_up_date.isoformat() if lead.follow_up_date else None,
    }


# ============= DEBUG ENDPOINTS =============

@router.get("/debug/scheduler")
async def debug_scheduler(db: AsyncSession = Depends(get_db)):
    """Debug endpoint to check scheduler status and auto-post settings."""
    from app.services.scheduler import scheduler
    
    # Get auto-post settings
    result = await db.execute(select(AutoPostSettings).limit(1))
    settings_row = result.scalar_one_or_none()
    
    # Get pending scheduled posts
    result = await db.execute(
        select(ScheduledPost)
        .where(ScheduledPost.status == "pending")
        .order_by(ScheduledPost.scheduled_time)
        .limit(10)
    )
    pending_posts = result.scalars().all()
    
    return {
        "scheduler_running": scheduler.running,
        "scheduler_jobs": [
            {"id": job.id, "next_run": str(job.next_run_time)}
            for job in scheduler.get_jobs()
        ],
        "auto_post_settings": {
            "exists": settings_row is not None,
            "enabled": settings_row.enabled if settings_row else False,
            "carousel_count": getattr(settings_row, 'carousel_count', 2) if settings_row else 2,
            "news_count": getattr(settings_row, 'news_count', 1) if settings_row else 1,
        } if settings_row else {"exists": False},
        "pending_posts_count": len(pending_posts),
        "pending_posts": [
            {
                "id": p.id,
                "scheduled_time": p.scheduled_time.isoformat() if p.scheduled_time else None,
                "post_type": getattr(p, 'post_type', 'carousel'),
                "status": p.status
            }
            for p in pending_posts
        ]
    }


@router.post("/debug/trigger-scheduler")
async def trigger_scheduler_check():
    """Manually trigger the scheduler check."""
    from app.services.scheduler import trigger_manual_check
    
    try:
        await trigger_manual_check()
        return {"status": "ok", "message": "Scheduler check triggered"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/emergency/stop")
async def emergency_stop(db: AsyncSession = Depends(get_db)):
    """EMERGENCY: Disable auto-posting and cancel all pending posts."""
    # Disable auto-posting
    result = await db.execute(select(AutoPostSettings).limit(1))
    settings_row = result.scalar_one_or_none()
    if settings_row:
        settings_row.enabled = False
    
    # Cancel all pending posts
    from sqlalchemy import update
    await db.execute(
        update(ScheduledPost)
        .where(ScheduledPost.status == "pending")
        .values(status="cancelled")
    )
    
    await db.commit()
    
    return {
        "status": "STOPPED",
        "message": "Auto-posting disabled, all pending posts cancelled"
    }
