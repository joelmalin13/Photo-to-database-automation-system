"""Document processing, retrieval, and lifecycle management service.

Orchestrates preprocessing, extraction, validation, duplicate checks,
and promotion of verified records into confirmed business tables.
"""

from __future__ import annotations

import io
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from fastapi import UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from config.settings import (
    ALLOWED_EXTENSIONS,
    MAX_IMAGE_SIZE_BYTES,
    DocumentCategory,
    DocumentStatus,
    logger,
)
from core.exceptions import ValidationError
from core.pipeline import ProcessResult, process_single_image
from db.crud import (
    delete_document as crud_delete_document,
    get_document_by_id,
    list_documents as crud_list_documents,
    promote_to_confirmed_record,
    update_document_raw_fields,
    update_document_status,
)
from db.models import Document


def sanitize_filename(filename: str) -> str:
    """Sanitize upload filename by stripping dangerous characters."""
    clean = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)
    return clean or f"upload_{uuid.uuid4().hex[:8]}.jpg"


class DocumentService:
    """Encapsulates business operations for ingested document records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def ingest_upload(
        self,
        file: UploadFile,
        category: str = "auto",
        preferred_engine: Optional[str] = None,
    ) -> ProcessResult:
        """Validate, store, and process an uploaded document image file."""
        filename = sanitize_filename(file.filename or "upload.jpg")
        content = await file.read()

        if len(content) == 0:
            raise ValidationError("Uploaded file is empty (0 bytes).")
        if len(content) > MAX_IMAGE_SIZE_BYTES:
            mb = len(content) / (1024 * 1024)
            raise ValidationError(f"File size ({mb:.1f}MB) exceeds 10MB limit.")

        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"File format '{ext}' unsupported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        try:
            with Image.open(io.BytesIO(content)) as img:
                img.verify()
        except Exception as exc:
            raise ValidationError(f"Corrupt or invalid image file: {exc}") from exc

        # Process through core pipeline
        result = process_single_image(
            image_bytes=content,
            filename=filename,
            doc_type=category,
            preferred_engine=preferred_engine,
            auto_save=True,
        )
        return result

    def get_document(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve full details of a single document by ID."""
        doc = get_document_by_id(self.db, doc_id)
        return doc.to_dict() if doc else None

    def list_documents(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch paginated, filtered documents formatted for views and API."""
        docs, total = crud_list_documents(
            session=self.db,
            category=category,
            status=status,
            search_query=search_query,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
        return [d.to_dict() for d in docs], total

    def update_fields(
        self, doc_id: int, fields: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update extracted attributes of a document."""
        doc = update_document_raw_fields(self.db, doc_id, fields)
        return doc.to_dict() if doc else None

    def approve_document(
        self,
        doc_id: int,
        verified_fields: Optional[Dict[str, Any]] = None,
        items: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Promote document from pending OCR to confirmed business tables upon verification.

        Rule: Never save unverified OCR output as confirmed data. Only approved records
        populate receipts, students, or business_cards tables.
        """
        doc = get_document_by_id(self.db, doc_id)
        if not doc:
            return None

        # If fields not supplied, use existing extracted fields
        if verified_fields is None:
            raw = doc.raw_fields_json or {}
            verified_fields = raw.get("fields", {})
            if items is None:
                items = raw.get("line_items", [])

        promoted_doc = promote_to_confirmed_record(
            session=self.db,
            doc_id=doc_id,
            verified_fields=verified_fields,
            items=items,
        )
        return promoted_doc.to_dict() if promoted_doc else None

    def reject_document(
        self, doc_id: int, reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Transition document status to rejected."""
        doc = update_document_status(
            self.db, doc_id, DocumentStatus.REJECTED.value, note=reason
        )
        return doc.to_dict() if doc else None

    def delete_document(self, doc_id: int) -> bool:
        """Delete document record and remove image from disk."""
        doc = get_document_by_id(self.db, doc_id)
        if not doc:
            return False

        # Attempt to remove disk file
        img_path = Path(doc.image_path)
        if img_path.exists():
            try:
                img_path.unlink()
            except OSError as exc:
                logger.warning("Could not delete image file %s: %s", img_path, exc)

        return crud_delete_document(self.db, doc_id)
