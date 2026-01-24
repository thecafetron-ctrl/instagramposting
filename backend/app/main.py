"""FastAPI app with API routes and frontend"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and scheduler on startup."""
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
    
    # Start the auto-posting scheduler
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
        print("✓ Auto-post scheduler started")
    except Exception as e:
        print(f"✗ Scheduler error: {e}")
    
    yield
    
    # Stop scheduler on shutdown
    print("Shutting down...")
    try:
        from app.services.scheduler import stop_scheduler
        stop_scheduler()
    except:
        pass

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

# Debug endpoint to verify API is working
@app.get("/api/debug")
def debug():
    return {
        "status": "ok",
        "routes_count": len(app.routes),
        "api_routes": [r.path for r in app.routes if hasattr(r, 'path') and r.path.startswith('/api')]
    }

# Import and include API routes
try:
    from app.routes import router
    app.include_router(router, prefix="/api")
    print("✓ API routes loaded")
    
    # Log all routes for debugging
    for route in app.routes:
        if hasattr(route, 'path'):
            print(f"  Route: {route.path}")
except Exception as e:
    print(f"✗ Failed to load routes: {e}")
    import traceback
    traceback.print_exc()

# Create directories - try multiple paths for compatibility
for img_dir in ["generated_images", "backend/generated_images"]:
    Path(img_dir).mkdir(exist_ok=True, parents=True)
Path("static").mkdir(exist_ok=True)

# Mount static files - find the correct images directory
images_dir = Path("generated_images")
if not images_dir.exists():
    images_dir = Path("backend/generated_images")
    images_dir.mkdir(exist_ok=True, parents=True)

print(f"✓ Serving images from: {images_dir.absolute()}")
app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")

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
