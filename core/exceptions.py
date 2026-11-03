"""Domain-specific exception hierarchy for PixelMind visual intelligence system.
"""

from __future__ import annotations


class PixelMindError(Exception):
    """Base exception for all PixelMind system errors."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DetectionError(PixelMindError):
    """Raised when YOLO inference or box rendering fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class EmbedderError(PixelMindError):
    """Raised when CLIP embedding extraction or similarity computation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class DuplicateImageError(PixelMindError):
    """Raised when an identical image has already been ingested (SHA-256 collision)."""

    def __init__(self, message: str, existing_id: int) -> None:
        super().__init__(message, status_code=409)
        self.existing_id = existing_id


class InvalidImageError(PixelMindError):
    """Raised when an uploaded file is empty, corrupt, or unsupported."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class QueryParseError(PixelMindError):
    """Raised when a natural language query cannot be parsed into a database query."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)
