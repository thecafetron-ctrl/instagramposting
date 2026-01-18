"""
Main FastAPI application for Instagram Carousel Generator.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pathlib import Path
import mimetypes

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

# Ensure directories exist
Path("generated_images").mkdir(exist_ok=True)
Path("static").mkdir(exist_ok=True)

# API routes
app.include_router(router, prefix="/api")

# Generated images
app.mount("/images", StaticFiles(directory="generated_images"), name="images")

# Health
@app.get("/health")
def health():
    return {"status": "ok"}

# Debug endpoint
@app.get("/debug/static")
def debug_static():
    static = Path("static")
    files = []
    if static.exists():
        for f in static.rglob("*"):
            if f.is_file():
                files.append(str(f.relative_to(static)))
    return {"files": files[:50], "total": len(files)}

# Serve frontend - mount AFTER API routes
# This serves everything from /static as root
@app.get("/")
async def root():
    index = Path("static/index.html")
    if index.exists():
        return HTMLResponse(index.read_text(), media_type="text/html")
    return {"message": "API running", "frontend": "not found"}

@app.get("/{path:path}")
async def serve_static(path: str):
    # Don't handle API or images
    if path.startswith("api/") or path.startswith("images/") or path == "health":
        return JSONResponse({"error": "not found"}, 404)
    
    static_file = Path("static") / path
    
    # Serve exact file if exists
    if static_file.exists() and static_file.is_file():
        mime_type, _ = mimetypes.guess_type(str(static_file))
        return FileResponse(static_file, media_type=mime_type)
    
    # SPA fallback
    index = Path("static/index.html")
    if index.exists():
        return HTMLResponse(index.read_text(), media_type="text/html")
    
    return JSONResponse({"error": "not found"}, 404)
