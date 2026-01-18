"""
Main FastAPI application for Instagram Carousel Generator.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
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
    print("=" * 50)
    print("Starting Instagram Carousel Generator...")
    print(f"PORT: {os.environ.get('PORT', 'not set')}")
    print("=" * 50)
    
    # Create directories
    Path("generated_images").mkdir(exist_ok=True)
    Path("assets").mkdir(exist_ok=True)
    Path("assets/fonts/Montserrat").mkdir(parents=True, exist_ok=True)
    Path("static").mkdir(exist_ok=True)
    
    # Check static files
    static_path = Path("static")
    print(f"Static path exists: {static_path.exists()}")
    if static_path.exists():
        print(f"Static contents: {list(static_path.iterdir())[:10]}")
    
    # Initialize database (with timeout)
    try:
        import asyncio
        await asyncio.wait_for(init_db(), timeout=30)
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database init error (will retry on first request): {e}")
    
    print("=" * 50)
    print("Application ready!")
    print("=" * 50)
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

# Include API routes FIRST
app.include_router(router, prefix="/api")

# Mount generated images
Path("generated_images").mkdir(exist_ok=True)
app.mount("/images", StaticFiles(directory="generated_images"), name="images")


# Simple health check at root level
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "instagram-carousel-generator"}


# Frontend serving - check at runtime
@app.get("/", response_class=HTMLResponse)
async def serve_root():
    """Serve frontend or API info"""
    static_index = Path("static/index.html")
    if static_index.exists():
        return FileResponse(static_index)
    return JSONResponse({
        "name": "Instagram Carousel Generator API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    })


# Serve static assets
@app.get("/assets/{file_path:path}")
async def serve_assets(file_path: str):
    """Serve static assets"""
    full_path = Path("static/assets") / file_path
    if full_path.exists() and full_path.is_file():
        return FileResponse(full_path)
    return JSONResponse({"error": "Not found"}, status_code=404)


# SPA catch-all (must be last)
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve SPA - return index.html for client-side routing"""
    # Skip API and known paths
    if full_path.startswith("api/") or full_path.startswith("images/"):
        return JSONResponse({"error": "Not found"}, status_code=404)
    
    # Try to serve the exact file
    file_path = Path("static") / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    # Fall back to index.html for SPA routing
    static_index = Path("static/index.html")
    if static_index.exists():
        return FileResponse(static_index)
    
    return JSONResponse({"error": "Frontend not found"}, status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
