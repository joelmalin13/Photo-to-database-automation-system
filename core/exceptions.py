"""Domain exception definitions for SnapBase application.

Defines a clean exception hierarchy for extraction, validation,
image processing, duplicate detection, and database operations.
"""

from __future__ import annotations


class SnapBaseError(Exception):
    """Base exception for all domain-specific SnapBase errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ExtractionError(SnapBaseError):
    """Raised when text or structured extraction from an image fails."""


class ValidationError(SnapBaseError):
    """Raised when extracted field data fails schema or type validation."""


class DuplicateImageError(SnapBaseError):
    """Raised when an identical image has already been ingested into the system."""

    def __init__(
        self,
        message: str,
        image_hash: str,
        existing_document_id: int | None = None,
    ) -> None:
        super().__init__(
            message,
            {"image_hash": image_hash, "document_id": existing_document_id},
        )
        self.image_hash = image_hash
        self.existing_document_id = existing_document_id


class PreprocessError(SnapBaseError):
    """Raised when image preprocessing (rotation, contrast, etc.) encounters an issue."""


class DatabaseError(SnapBaseError):
    """Raised when an unexpected error occurs during database operations."""
