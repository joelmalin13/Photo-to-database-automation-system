"""Orchestrator pipeline connecting validation, preprocessing, extraction, and persistence.

Implements single and generator-based batch document processing workflows
with automated error fallback, duplicate detection, and Pandas data cleaning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Any, Dict, Generator, List, Optional, Tuple
import uuid

from config.settings import (
    DocumentCategory,
    DocumentStatus,
    UPLOAD_DIR,
    load_schemas,
    logger,
)
from core.cleaner import clean_document_record
from core.exceptions import (
    ExtractionError,
    PreprocessError,
    ValidationError,
)
from core.extractor_base import BaseExtractor, detect_document_type, get_extractor
from core.normalize import normalize_fields
from core.preprocess import (
    compute_image_hash,
    preprocess_image,
    validate_image_bytes,
)
from core.validators import validate_extracted_fields
from db.crud import create_document, find_document_by_hash
from db.session import get_db_session


@dataclass
class ProcessResult:
    """Structured outcome for an ingested document photo."""

    filename: str
    doc_type: str
    image_hash: str
    status: str = DocumentStatus.PROCESSED.value
    document_id: Optional[int] = None
    image_path: str = ""
    fields: Dict[str, Any] = field(default_factory=dict)
    confidences: Dict[str, float] = field(default_factory=dict)
    line_items: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    engine_used: str = "EasyOCR"
    is_duplicate: bool = False
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    word_confidences: List[Dict[str, Any]] = field(default_factory=list)


def _resolve_schema(
    doc_type: str, schemas: Dict[str, Any]
) -> Tuple[str, Dict[str, Any]]:
    """Resolve target document category and retrieve its configuration schema."""
    target_type = doc_type if doc_type not in ("auto", "other", None) else "receipts"
    if target_type == "receipt_invoice":
        target_type = "receipts"
    elif target_type in ("student_marksheet", "student_id_form"):
        target_type = "students"
    elif target_type == "business_card":
        target_type = "business_cards"

    schema = schemas.get(target_type) or schemas.get("receipts", {})
    return target_type, schema


def _run_extraction_with_fallback(
    extractor: BaseExtractor,
    image_path: Path,
    target_type: str,
    schema: Dict[str, Any],
) -> Tuple[Any, List[str]]:
    """Execute primary extraction with automated fallback to default EasyOCR upon failure."""
    warnings: List[str] = []
    try:
        result = extractor.extract(image_path, target_type, schema)
        return result, warnings
    except Exception as exc:
        logger.warning(
            "Primary extraction failed: %s. Attempting EasyOCR fallback.",
            exc,
        )
        warnings.append(
            f"Extraction encountered an issue ({exc}); used default EasyOCR fallback."
        )
        from core.ocr_extractor import OCRExtractor

        fallback_engine = OCRExtractor()
        result = fallback_engine.extract(image_path, target_type, schema)
        return result, warnings


def process_single_image(
    image_bytes: bytes,
    filename: str,
    doc_type: str = "auto",
    preferred_engine: Optional[str] = None,
    auto_save: bool = True,
) -> ProcessResult:
    """Execute end-to-end processing: validate, hash, preprocess, extract, clean, and save."""
    start_time = time.time()
    schemas = load_schemas()
    try:
        validate_image_bytes(image_bytes, filename)
    except ValidationError as err:
        return ProcessResult(
            filename=filename,
            doc_type=doc_type,
            image_hash="",
            error_message=str(err),
            status=DocumentStatus.FAILED.value,
        )

    image_hash = compute_image_hash(image_bytes)

    # Duplicate check
    with get_db_session() as session:
        existing = find_document_by_hash(session, image_hash)
        if existing:
            raw_data = existing.raw_fields_json or {}
            return ProcessResult(
                filename=filename,
                doc_type=existing.category,
                image_hash=image_hash,
                status=existing.status,
                document_id=existing.id,
                image_path=existing.image_path,
                fields=raw_data.get("fields", {}),
                confidences=raw_data.get("confidences", {}),
                line_items=raw_data.get("line_items", []),
                warnings=[
                    f"Duplicate image already ingested on {existing.created_at.strftime('%Y-%m-%d %H:%M')} (ID: #{existing.id})."
                ],
                is_duplicate=True,
                engine_used=raw_data.get("engine_used", "EasyOCR"),
            )

    # Unique destination filename avoiding overwriting
    save_filename = f"{uuid.uuid4().hex[:10]}_{Path(filename).name}"
    processed_path = UPLOAD_DIR / save_filename
    _, meta = preprocess_image(image_bytes, processed_path)

    warnings: List[str] = []
    if meta.get("is_blurry"):
        warnings.append(
            f"Image is blurry (Laplacian variance: {meta.get('blur_score')}). Consider recapturing in better lighting."
        )

    target_type, schema = _resolve_schema(doc_type, schemas)
    extractor = get_extractor(preferred_engine)
    raw_res, fallback_warns = _run_extraction_with_fallback(
        extractor, processed_path, doc_type, schema
    )
    warnings.extend(fallback_warns)

    if raw_res.doc_type in schemas:
        target_type = raw_res.doc_type
        schema = schemas.get(target_type, schema)

    # Normalize fields (Dates, currency floats)
    norm_fields = normalize_fields(raw_res.fields, schema.get("fields", []))

    # Clean data via Pandas pipeline
    cleaned_fields, clean_warns = clean_document_record(norm_fields, target_type)
    warnings.extend(clean_warns)

    # Validate against schema contracts & compute confidences
    valid_fields, confidences, val_warnings = validate_extracted_fields(
        target_type, cleaned_fields, raw_res.confidences, schema
    )
    warnings.extend(val_warnings)

    # Overall OCR average confidence
    avg_conf = (
        sum(confidences.values()) / len(confidences) if confidences else 0.75
    )

    execution_ms = int((time.time() - start_time) * 1000)

    doc_id = None
    if auto_save:
        with get_db_session() as session:
            doc = create_document(
                session=session,
                filename=filename,
                image_path=str(processed_path),
                image_hash=image_hash,
                category=target_type,
                ocr_text=raw_res.raw_text,
                ocr_confidence=avg_conf,
                status=DocumentStatus.PROCESSED.value,
                raw_fields={
                    "fields": valid_fields,
                    "confidences": confidences,
                    "line_items": raw_res.line_items,
                    "engine_used": raw_res.engine_used,
                    "word_confidences": raw_res.word_confidences,
                },
                execution_time_ms=execution_ms,
            )
            doc_id = doc.id

    return ProcessResult(
        document_id=doc_id,
        filename=filename,
        doc_type=target_type,
        status=DocumentStatus.PROCESSED.value,
        image_path=str(processed_path),
        image_hash=image_hash,
        fields=valid_fields,
        confidences=confidences,
        line_items=raw_res.line_items,
        warnings=warnings,
        engine_used=raw_res.engine_used,
        metadata=meta,
        word_confidences=raw_res.word_confidences,
    )


def batch_process_images(
    image_items: List[Tuple[bytes, str]],
    doc_type: str = "auto",
    preferred_engine: Optional[str] = None,
) -> Generator[ProcessResult, None, None]:
    """Process an iterable collection of images sequentially using a generator."""
    for img_bytes, fname in image_items:
        try:
            result = process_single_image(
                image_bytes=img_bytes,
                filename=fname,
                doc_type=doc_type,
                preferred_engine=preferred_engine,
                auto_save=True,
            )
            yield result
        except Exception as exc:
            logger.error("Error processing batch item %s: %s", fname, exc)
            yield ProcessResult(
                filename=fname,
                doc_type=doc_type,
                image_hash="",
                status=DocumentStatus.FAILED.value,
                error_message=str(exc),
            )
