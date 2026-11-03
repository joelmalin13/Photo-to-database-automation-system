"""FastAPI dependency injection utilities for PixelMind.
"""

from __future__ import annotations

from typing import Generator
from sqlalchemy.orm import Session
from db.session import get_db

__all__ = ["get_db"]
