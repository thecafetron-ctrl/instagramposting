from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    topic_api_url: str = "http://localhost:8001/topics"
    enrichment_api_url: str = "http://localhost:8001/enrich"
    openai_api_key: str = ""  # Set via OPENAI_API_KEY env var
    serpapi_key: str = ""  # Set via SERPAPI_KEY env var
    brand_name: str = "STRUCTURE"
    deduplication_window: int = 30
    
    # Neon PostgreSQL database
    database_url: str = ""  # Set via DATABASE_URL env var
    
    # Instagram API
    instagram_app_id: str = ""  # Set via INSTAGRAM_APP_ID env var
    instagram_app_secret: str = ""  # Set via INSTAGRAM_APP_SECRET env var
    instagram_access_token: str = ""  # Set via INSTAGRAM_ACCESS_TOKEN env var
    
    # YouTube API
    youtube_api_key: str = ""  # Set via YOUTUBE_API_KEY env var
    youtube_client_id: str = ""  # Set via YOUTUBE_CLIENT_ID env var
    youtube_client_secret: str = ""  # Set via YOUTUBE_CLIENT_SECRET env var
    youtube_refresh_token: str = ""  # Set via YOUTUBE_REFRESH_TOKEN env var
    
    # TikTok API
    tiktok_client_key: str = ""  # Set via TIKTOK_CLIENT_KEY env var
    tiktok_client_secret: str = ""  # Set via TIKTOK_CLIENT_SECRET env var
    tiktok_access_token: str = ""  # Set via TIKTOK_ACCESS_TOKEN env var
    tiktok_redirect_uri: str = "https://mccarthydemo.site/tiktok/callback"  # Your domain
    
    # Unsplash API
    unsplash_access_key: str = ""  # Set via UNSPLASH_ACCESS_KEY env var
    unsplash_secret_key: str = ""  # Set via UNSPLASH_SECRET_KEY env var
    
    # Assets
    background_image_path: str = "assets/background.png"
    logo_image_path: str = "assets/logo.png"
    logo_svg_path: str = "assets/logo.svg"
    font_path: str = "assets/fonts/Montserrat"
    
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
