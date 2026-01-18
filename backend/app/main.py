"""Minimal FastAPI app for testing"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import mimetypes

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

@app.get("/")
def root():
    index = Path("static/index.html")
    if index.exists():
        return HTMLResponse(index.read_text())
    return {"error": "no index.html", "cwd": str(Path.cwd())}

@app.get("/{path:path}")
def catch_all(path: str):
    if path in ("health", "test"):
        return JSONResponse({"error": "not found"}, 404)
    
    f = Path("static") / path
    if f.exists() and f.is_file():
        mime, _ = mimetypes.guess_type(str(f))
        return FileResponse(f, media_type=mime)
    
    # SPA fallback
    index = Path("static/index.html")
    if index.exists():
        return HTMLResponse(index.read_text())
    
    return JSONResponse({"error": "not found", "path": path}, 404)
