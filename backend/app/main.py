"""
Main FastAPI application for Instagram Carousel Generator.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import os

from app.routes import router

app = FastAPI(title="Instagram Carousel Generator", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories
Path("generated_images").mkdir(exist_ok=True)
Path("static").mkdir(exist_ok=True)

# API routes FIRST
app.include_router(router, prefix="/api")

# Mount generated images
app.mount("/images", StaticFiles(directory="generated_images"), name="images")

# Health check
@app.get("/health")
@app.get("/api/health") 
def health():
    return {"status": "ok"}

# Mount static assets BEFORE catch-all
static_path = Path("static")
if static_path.exists():
    # Mount the assets subfolder for JS/CSS
    assets_path = static_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

# Serve index.html for root
@app.get("/")
async def serve_index():
    index_path = Path("static/index.html")
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    return JSONResponse({"error": "Frontend not built"}, status_code=404)

# SPA catch-all - serve index.html for all other routes
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Skip API routes
    if full_path.startswith("api") or full_path.startswith("images") or full_path.startswith("assets"):
        return JSONResponse({"error": "Not found"}, status_code=404)
    
    # Try exact file first
    file_path = Path("static") / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    # Fall back to index.html for SPA routing
    index_path = Path("static/index.html")
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    
    return JSONResponse({"error": "Not found"}, status_code=404)
