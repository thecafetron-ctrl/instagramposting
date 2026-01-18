"""FastAPI app with API routes and frontend"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    print("Starting app...")
    
    # Import models FIRST so tables are registered
    from app import models  # noqa
    
    # Then initialize database
    from app.database import init_db
    try:
        await init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"✗ Database error: {e}")
    
    yield
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
def health():
    return {"status": "ok"}

# Import and include API routes
try:
    from app.routes import router
    app.include_router(router, prefix="/api")
    print("✓ API routes loaded")
except Exception as e:
    print(f"✗ Failed to load routes: {e}")
    import traceback
    traceback.print_exc()

# Create directories
Path("generated_images").mkdir(exist_ok=True)
Path("static").mkdir(exist_ok=True)

# Mount static files
app.mount("/images", StaticFiles(directory="generated_images"), name="images")

# Mount frontend assets
if Path("static/assets").exists():
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

# Serve frontend
@app.get("/")
def root():
    index = Path("static/index.html")
    if index.exists():
        return HTMLResponse(index.read_text())
    return {"error": "Frontend not found"}

@app.get("/{path:path}")
def catch_all(path: str):
    # Don't catch API or assets
    if path.startswith("api") or path.startswith("assets") or path.startswith("images"):
        return JSONResponse({"error": "not found"}, 404)
    
    # SPA fallback
    index = Path("static/index.html")
    if index.exists():
        return HTMLResponse(index.read_text())
    return JSONResponse({"error": "not found"}, 404)
