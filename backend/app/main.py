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

# Create app WITHOUT lifespan to avoid blocking
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

# API routes
app.include_router(router, prefix="/api")

# Images
app.mount("/images", StaticFiles(directory="generated_images"), name="images")

# Health check
@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}

# Frontend
@app.get("/")
async def root():
    index = Path("static/index.html")
    if index.exists():
        return FileResponse(index)
    return {"api": "running", "frontend": "not found"}

@app.get("/assets/{path:path}")
async def assets(path: str):
    f = Path(f"static/assets/{path}")
    if f.exists():
        return FileResponse(f)
    return JSONResponse({"error": "not found"}, 404)

@app.get("/{path:path}")
async def spa(path: str):
    if path.startswith("api") or path.startswith("images"):
        return JSONResponse({"error": "not found"}, 404)
    f = Path(f"static/{path}")
    if f.exists() and f.is_file():
        return FileResponse(f)
    index = Path("static/index.html")
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"error": "not found"}, 404)
