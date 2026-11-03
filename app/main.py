"""FastAPI application factory, router registration, and lifecycle orchestration for PixelMind.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers.api import router as api_router
from app.routers.pages import router as pages_router
from config.settings import ANNOTATED_DIR, BASE_DIR, DATA_DIR, UPLOAD_DIR, logger
from core.exceptions import PixelMindError
from db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle manager for the FastAPI server."""
    logger.info("PixelMind AI Visual Intelligence server starting up...")
    try:
        init_db()
    except Exception as exc:
        logger.error("Database initialization encountered an error: %s", exc)

    yield
    logger.info("PixelMind AI Visual Intelligence server shutting down...")


app = FastAPI(
    title="PIXELMIND: AI-Powered Visual Intelligence Database",
    description="Every Image Has Data. Make It Searchable.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Cross-Origin Resource Sharing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static asset directory (checks public/static first for Vercel, falls back to app/static)
static_dir = BASE_DIR / "public" / "static"
if not static_dir.exists():
    static_dir = BASE_DIR / "app" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Local media asset directories (mounted safely if directories exist)
if UPLOAD_DIR.exists():
    app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
if ANNOTATED_DIR.exists():
    app.mount("/annotated", StaticFiles(directory=str(ANNOTATED_DIR)), name="annotated")

# Health check endpoint for deployment verification
@app.get("/health", tags=["Health"], summary="Deployment health check")
def root_health_check() -> Dict[str, Any]:
    """Root health endpoint for monitoring, uptime verification, and deployment sanity."""
    from config.settings import (
        AI_MODE,
        GEMINI_API_KEY,
        GEMINI_EMBED_MODEL,
        GEMINI_MODEL,
        IS_VERCEL,
        STORAGE_BACKEND,
        SUPABASE_URL,
    )
    from db.session import get_db_status
    db_stat = get_db_status()
    is_healthy = db_stat.get("connected", False)
    return {
        "status": "healthy" if is_healthy else "degraded",
        "mode": AI_MODE,
        "is_vercel": IS_VERCEL,
        "database": db_stat,
        "storage": {
            "backend": STORAGE_BACKEND,
            "status": "ready",
        },
        "ai": {
            "detector": GEMINI_MODEL if AI_MODE == "cloud" else "YOLOv8n",
            "embedder": GEMINI_EMBED_MODEL if AI_MODE == "cloud" else "CLIP ViT-B-32",
            "gemini_configured": bool(GEMINI_API_KEY),
            "supabase_configured": bool(SUPABASE_URL),
        },
    }

# Include HTML page and REST API routers
app.include_router(pages_router)
app.include_router(api_router)


# Global Exception Handlers
@app.exception_handler(PixelMindError)
async def pixelmind_exception_handler(request: Request, exc: PixelMindError) -> JSONResponse:
    """Format domain-specific application errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.message, "type": exc.__class__.__name__},
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Any) -> Any:
    """Friendly 404 response handler."""
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "error": "Requested resource was not found."},
        )
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head><title>404 - Not Found | PixelMind</title><script src="https://cdn.tailwindcss.com"></script></head>
        <body class="bg-gray-50 flex items-center justify-center min-h-screen">
          <div class="text-center p-8 bg-white rounded-2xl shadow-sm border border-gray-200 max-w-md">
            <h1 class="text-4xl font-bold text-gray-900 mb-2">404</h1>
            <p class="text-gray-600 mb-6">The page or resource you are looking for does not exist.</p>
            <a href="/" class="px-5 py-2.5 bg-[#C62828] text-white rounded-lg font-medium hover:bg-red-700 transition">Return to Dashboard</a>
          </div>
        </body>
        </html>
        """,
        status_code=status.HTTP_404_NOT_FOUND,
    )
