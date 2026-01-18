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
    
    # Post settings (for generating on-the-fly or overriding)
    template_id = Column(String(50), nullable=True)  # None = random
    color_theme = Column(String(50), nullable=True)  # None = random
    texture = Column(String(50), nullable=True)  # None = random
    layout = Column(String(50), nullable=True)  # None = random
    slide_count = Column(Integer, default=4)
    
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
    
    # Default settings for auto-generated posts
    default_template_id = Column(String(50), nullable=True)  # None = random
    default_color_theme = Column(String(50), nullable=True)  # None = random
    default_texture = Column(String(50), nullable=True)  # None = random
    default_layout = Column(String(50), nullable=True)  # None = random
    default_slide_count = Column(Integer, default=4)
    
    # Instagram credentials (stored securely)
    instagram_username = Column(String(100), nullable=True)
    instagram_password = Column(Text, nullable=True)  # Should be encrypted in production
    
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
