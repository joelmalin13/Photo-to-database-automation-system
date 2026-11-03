"""FastAPI application factory, middleware, and lifecycle configuration.

Bootstraps the SnapBase web platform, configures static asset hosting,
initializes the SQLite database, and handles unified error dispatching.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers.api import api_router
from app.routers.pages import pages_router
from config.settings import BASE_DIR, logger
from core.exceptions import SnapBaseError
from db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Execute idempotent database initialization on application startup."""
    logger.info("SnapBase FastAPI server starting up...")
    init_db()
    yield
    logger.info("SnapBase FastAPI server shutting down...")


app = FastAPI(
    title="SnapBase API",
    description="Photo to Database Automation Platform REST API and Web Portal",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Asset Mounting
static_dir = BASE_DIR / "app" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.exception_handler(SnapBaseError)
async def snapbase_error_handler(
    request: Request, exc: SnapBaseError
) -> JSONResponse | HTMLResponse:
    """Format domain-specific application errors gracefully."""
    logger.error("SnapBaseError intercepted: %s", exc)
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": exc.message, "details": exc.details},
        )
    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html>
        <head><title>SnapBase Error</title>
        <script src="https://cdn.tailwindcss.com"></script></head>
        <body class="bg-gray-50 flex items-center justify-center min-h-screen">
          <div class="bg-white p-8 rounded-xl shadow-sm border max-w-md text-center">
            <div class="text-red-600 text-3xl font-bold mb-2">Error Encountered</div>
            <p class="text-gray-600 mb-6">{exc.message}</p>
            <a href="/" class="px-4 py-2 bg-red-700 text-white rounded-lg font-medium">Return Home</a>
          </div>
        </body>
        </html>
        """,
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse | HTMLResponse:
    """Format HTTP errors with custom UI for pages and JSON for APIs."""
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html>
        <head><title>Error {exc.status_code}</title>
        <script src="https://cdn.tailwindcss.com"></script></head>
        <body class="bg-gray-50 flex items-center justify-center min-h-screen">
          <div class="bg-white p-8 rounded-xl shadow-sm border max-w-md text-center">
            <div class="text-gray-900 text-4xl font-extrabold mb-2">{exc.status_code}</div>
            <p class="text-gray-600 mb-6">{exc.detail}</p>
            <a href="/" class="px-4 py-2 bg-red-700 text-white rounded-lg font-medium">Return Home</a>
          </div>
        </body>
        </html>
        """,
        status_code=exc.status_code,
    )


# Register Routers
app.include_router(pages_router)
app.include_router(api_router)
