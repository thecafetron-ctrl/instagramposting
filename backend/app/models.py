from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, Float
from sqlalchemy.sql import func
from app.database import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(500), nullable=False, index=True)
    template_id = Column(String(50), nullable=False)
    slide_1_text = Column(Text, nullable=False)
    slide_2_text = Column(Text, nullable=False)
    slide_3_text = Column(Text, nullable=False)
    slide_4_text = Column(Text, nullable=False)
    caption = Column(Text, nullable=False)
    hashtags = Column(Text, nullable=False)
    slide_1_image = Column(String(500), nullable=True)
    slide_2_image = Column(String(500), nullable=True)
    slide_3_image = Column(String(500), nullable=True)
    slide_4_image = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata_json = Column(JSON, nullable=True)


class UsedTopic(Base):
    __tablename__ = "used_topics"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(500), nullable=False, index=True)
    post_id = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ScheduledPost(Base):
    """Posts scheduled for auto-posting to Instagram."""
    __tablename__ = "scheduled_posts"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, nullable=True)  # Link to generated post (optional, can generate on-the-fly)
    scheduled_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), default="pending")  # pending, posted, failed, cancelled
    post_type = Column(String(20), default="carousel")  # carousel or news
    
    # Post settings (for generating on-the-fly or overriding)
    template_id = Column(String(50), nullable=True)  # None = random
    color_theme = Column(String(50), nullable=True)  # None = random
    texture = Column(String(50), nullable=True)  # None = random
    layout = Column(String(50), nullable=True)  # None = random
    slide_count = Column(Integer, default=4)
    
    # News post settings
    news_accent_color = Column(String(50), nullable=True)
    news_time_range = Column(String(20), nullable=True)
    news_auto_select = Column(Boolean, nullable=True)
    
    # Result tracking
    instagram_post_id = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AutoPostSettings(Base):
    """Settings for automatic posting."""
    __tablename__ = "auto_post_settings"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=False)
    posts_per_day = Column(Integer, default=3)
    
    # Post type distribution
    carousel_count = Column(Integer, default=2)  # Number of carousels per day
    news_count = Column(Integer, default=1)  # Number of news posts per day
    equal_distribution = Column(Boolean, default=True)  # Spread posts equally throughout day
    
    # Default settings for auto-generated carousel posts
    default_template_id = Column(String(50), nullable=True)  # None = random
    default_color_theme = Column(String(50), nullable=True)  # None = random
    default_texture = Column(String(50), nullable=True)  # None = random
    default_layout = Column(String(50), nullable=True)  # None = random
    default_slide_count = Column(Integer, default=4)
    
    # Default settings for news posts
    news_accent_color = Column(String(50), default="cyan")
    news_time_range = Column(String(20), default="1d")
    news_auto_select = Column(Boolean, default=True)
    
    # Instagram credentials (stored securely)
    instagram_username = Column(String(100), nullable=True)
    instagram_password = Column(Text, nullable=True)  # Should be encrypted in production
    
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Lead(Base):
    """Track leads from Instagram posts."""
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    
    # Lead info
    name = Column(String(200), nullable=False)
    instagram_handle = Column(String(100), nullable=True)
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    company = Column(String(200), nullable=True)
    
    # Status tracking
    status = Column(String(50), default="new")  # new, no_answer, follow_up, booked, closed, lost
    follow_up_date = Column(DateTime(timezone=True), nullable=True)
    
    # Source tracking
    source_post_id = Column(Integer, nullable=True)  # Which post they came from
    source = Column(String(100), nullable=True)  # e.g. "Instagram DM", "Comment", etc.
    
    # Notes
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
