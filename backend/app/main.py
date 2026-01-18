"""
Main FastAPI application for Instagram Carousel Generator.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
import os

from app.database import init_db
from app.routes import router
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    
    # Create directories
    Path("generated_images").mkdir(exist_ok=True)
    Path("assets").mkdir(exist_ok=True)
    Path("assets/fonts/Montserrat").mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Shutdown
    pass


app = FastAPI(
    title="Instagram Carousel Generator",
    description="Generate Instagram carousel posts for logistics + AI content",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for generated images
if Path("generated_images").exists():
    app.mount("/images", StaticFiles(directory="generated_images"), name="images")

# Include API routes
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Instagram Carousel Generator",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
