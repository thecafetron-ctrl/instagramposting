#!/usr/bin/env python3
"""
Start the Instagram Carousel Generator server.
"""

import uvicorn
from app.config import get_settings

settings = get_settings()

if __name__ == "__main__":
    print("=" * 50)
    print("Instagram Carousel Generator")
    print("=" * 50)
    print(f"Starting server at http://{settings.host}:{settings.port}")
    print(f"API Docs: http://localhost:{settings.port}/docs")
    print("=" * 50)
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
