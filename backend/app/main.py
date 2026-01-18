"""Minimal FastAPI app"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/test")
def test():
    static = Path("static")
    files = list(static.rglob("*"))[:20] if static.exists() else []
    return {
        "static_exists": static.exists(),
        "files": [str(f) for f in files],
        "index_exists": (static / "index.html").exists()
    }

# Mount static files - this handles all the JS/CSS with proper MIME types
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

@app.get("/")
def root():
    index = Path("static/index.html")
    if index.exists():
        return HTMLResponse(index.read_text())
    return {"error": "no index.html"}

@app.get("/{path:path}")
def catch_all(path: str):
    # SPA fallback - return index.html for all other routes
    index = Path("static/index.html")
    if index.exists():
        return HTMLResponse(index.read_text())
    return JSONResponse({"error": "not found"}, 404)
