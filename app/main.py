"""FastAPI application factory, router registration, and lifecycle orchestration for PixelMind.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
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

# Static and media asset directories
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/annotated", StaticFiles(directory=str(ANNOTATED_DIR)), name="annotated")

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
        status_code=404,
    )
