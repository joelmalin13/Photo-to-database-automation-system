"""Vercel Serverless Entrypoint for PixelMind AI Visual Intelligence Database.

Exposes the ASGI FastAPI application instance to Vercel's Python runtime.
"""

from app.main import app

# Vercel looks for 'app' as the ASGI application entrypoint
__all__ = ["app"]
