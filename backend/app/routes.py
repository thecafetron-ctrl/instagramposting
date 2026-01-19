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
from app.services.instagram_poster import post_carousel_to_instagram, verify_access_token
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
    default_template_id: Optional[str] = None
    default_color_theme: Optional[str] = None
    default_texture: Optional[str] = None
    default_layout: Optional[str] = None
    default_slide_count: int = 4
    instagram_username: Optional[str] = None
    instagram_password: Optional[str] = None


class AutoPostSettingsResponse(BaseModel):
    id: int
    enabled: bool
    posts_per_day: int
    default_template_id: Optional[str]
    default_color_theme: Optional[str]
    default_texture: Optional[str]
    default_layout: Optional[str]
    default_slide_count: int
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
    template_id: Optional[str]
    color_theme: Optional[str]
    texture: Optional[str]
    layout: Optional[str]
    slide_count: int
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
                default_slide_count=4
            )
            db.add(settings_row)
            await db.commit()
            await db.refresh(settings_row)
        
        return AutoPostSettingsResponse(
            id=settings_row.id,
            enabled=settings_row.enabled,
            posts_per_day=settings_row.posts_per_day,
            default_template_id=settings_row.default_template_id,
            default_color_theme=settings_row.default_color_theme,
            default_texture=settings_row.default_texture,
            default_layout=settings_row.default_layout,
            default_slide_count=settings_row.default_slide_count,
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
            default_template_id=None,
            default_color_theme=None,
            default_texture=None,
            default_layout=None,
            default_slide_count=4,
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
    settings_row.default_template_id = request.default_template_id
    settings_row.default_color_theme = request.default_color_theme
    settings_row.default_texture = request.default_texture
    settings_row.default_layout = request.default_layout
    settings_row.default_slide_count = request.default_slide_count
    
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
        default_template_id=settings_row.default_template_id,
        default_color_theme=settings_row.default_color_theme,
        default_texture=settings_row.default_texture,
        default_layout=settings_row.default_layout,
        default_slide_count=settings_row.default_slide_count,
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
            template_id=p.template_id,
            color_theme=p.color_theme,
            texture=p.texture,
            layout=p.layout,
            slide_count=p.slide_count or 4,
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
    
    posts_per_day = settings_row.posts_per_day
    interval_hours = 24 / posts_per_day
    
    # Clear existing pending posts for today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # Get available options for randomization
    templates = get_all_templates()
    template_ids = [t["id"] for t in templates]
    color_theme_ids = list(COLOR_THEMES.keys())
    texture_ids = list(BACKGROUND_TEXTURES.keys())
    layout_ids = list(LAYOUT_STYLES.keys())
    
    created_posts = []
    
    for i in range(posts_per_day):
        scheduled_time = today_start + timedelta(hours=interval_hours * i + interval_hours / 2)
        
        # Use defaults or randomize
        template_id = settings_row.default_template_id or random.choice(template_ids)
        color_theme = settings_row.default_color_theme or random.choice(color_theme_ids)
        texture = settings_row.default_texture or random.choice(texture_ids)
        layout = settings_row.default_layout or weighted_layout_choice(layout_ids)
        slide_count = settings_row.default_slide_count or 4
        
        scheduled_post = ScheduledPost(
            scheduled_time=scheduled_time,
            status="pending",
            template_id=template_id,
            color_theme=color_theme,
            texture=texture,
            layout=layout,
            slide_count=slide_count
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
        "posts": [
            {
                "id": p.id,
                "scheduled_time": p.scheduled_time.isoformat(),
                "template_id": p.template_id,
                "color_theme": p.color_theme,
                "texture": p.texture,
                "layout": p.layout
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
    Post a generated carousel to Instagram using the Graph API.
    """
    # Get the post
    result = await db.execute(
        select(Post).where(Post.id == request.post_id)
    )
    post = result.scalar_one_or_none()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Collect all image paths (slides 1-4)
    image_paths = [
        post.slide_1_image,
        post.slide_2_image,
        post.slide_3_image,
        post.slide_4_image
    ]
    
    # Add any additional slides from metadata (slides 5+)
    if post.metadata_json and "extra_images" in post.metadata_json:
        extra_images = post.metadata_json["extra_images"]
        slide_count = post.metadata_json.get("slide_count", 4)
        for i in range(5, slide_count + 1):
            img_key = f"slide_{i}_image"
            if img_key in extra_images and extra_images[img_key]:
                image_paths.append(extra_images[img_key])
    
    # Filter out None values
    image_paths = [p for p in image_paths if p]
    
    if len(image_paths) < 2:
        raise HTTPException(
            status_code=400, 
            detail="Need at least 2 images for a carousel"
        )
    
    # Determine base URL for serving images
    # Use provided URL or try to get from environment
    import os
    base_url = request.base_url or os.environ.get("PUBLIC_URL", "https://instagramposting-production-4e91.up.railway.app")
    
    # Post to Instagram
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
