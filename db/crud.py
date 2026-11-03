"""CRUD operations for SnapBase documents, fields, and line items.

Provides transactional query helpers for document ingestion, duplicate
lookup, status updates, full-text field searches, filtering, and analytics.
"""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from config.settings import DocumentStatus, logger
from db.models import Document, DocumentField, LineItem, utc_now


def find_document_by_hash(session: Session, image_hash: str) -> Optional[Document]:
    """Locate an existing document with the given SHA-256 hash."""
    return session.query(Document).filter(Document.image_hash == image_hash).first()


def get_document_by_id(session: Session, doc_id: int) -> Optional[Document]:
    """Retrieve a single document by its primary key ID."""
    return session.query(Document).filter(Document.id == doc_id).first()


def create_document(
    session: Session,
    filename: str,
    image_path: str,
    image_hash: str,
    doc_type: str,
    status: str = DocumentStatus.PENDING.value,
    fields: Optional[Dict[str, Any]] = None,
    confidences: Optional[Dict[str, float]] = None,
    line_items: Optional[List[Dict[str, Any]]] = None,
) -> Document:
    """Persist a new document with its extracted fields and line items."""
    fields = fields or {}
    confidences = confidences or {}
    line_items = line_items or []

    doc = Document(
        filename=filename,
        image_path=image_path,
        image_hash=image_hash,
        type=doc_type,
        status=status,
        is_edited=False,
    )
    session.add(doc)
    session.flush()

    # Add fields
    for key, value in fields.items():
        conf = float(confidences.get(key, 1.0))
        field_obj = DocumentField(
            document_id=doc.id,
            key=key,
            value=str(value) if value is not None else None,
            confidence=conf,
            is_edited=False,
        )
        session.add(field_obj)

    # Add line items
    for idx, item in enumerate(line_items):
        item_obj = LineItem(
            document_id=doc.id,
            item_index=idx,
            data_json=json.dumps(item),
        )
        session.add(item_obj)

    session.flush()
    logger.info("Persisted document id=%d (%s, %s)", doc.id, filename, doc_type)
    return doc


def update_document_status(
    session: Session, doc_id: int, status: str
) -> Optional[Document]:
    """Update status of a document (e.g. approve, reject)."""
    doc = get_document_by_id(session, doc_id)
    if not doc:
        return None
    doc.status = status
    doc.updated_at = utc_now()
    session.flush()
    logger.info("Updated document %d status to %s", doc_id, status)
    return doc


def update_document_fields(
    session: Session,
    doc_id: int,
    updated_fields: Dict[str, Any],
    mark_edited: bool = True,
) -> Optional[Document]:
    """Update field values for an existing document and record edits."""
    doc = get_document_by_id(session, doc_id)
    if not doc:
        return None

    existing_fields = {f.key: f for f in doc.fields}
    changed = False

    for key, new_val in updated_fields.items():
        str_val = str(new_val) if new_val is not None else None
        if key in existing_fields:
            field_obj = existing_fields[key]
            if field_obj.value != str_val:
                field_obj.value = str_val
                field_obj.is_edited = True
                changed = True
        else:
            field_obj = DocumentField(
                document_id=doc.id,
                key=key,
                value=str_val,
                confidence=1.0,
                is_edited=True,
            )
            session.add(field_obj)
            changed = True

    if changed and mark_edited:
        doc.is_edited = True
    doc.updated_at = utc_now()
    session.flush()
    logger.info("Updated fields for document %d (is_edited=%s)", doc_id, doc.is_edited)
    return doc


def delete_document(session: Session, doc_id: int) -> bool:
    """Delete a document and cascade delete related fields and line items."""
    doc = get_document_by_id(session, doc_id)
    if not doc:
        return False
    session.delete(doc)
    session.flush()
    logger.info("Deleted document id=%d", doc_id)
    return True


def list_documents(
    session: Session,
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search_query: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 10,
) -> Tuple[List[Document], int]:
    """Filter, sort, search, and paginate documents."""
    query = session.query(Document)

    if doc_type and doc_type != "all":
        query = query.filter(Document.type == doc_type)
    if status and status != "all":
        query = query.filter(Document.status == status)
    if start_date:
        query = query.filter(Document.created_at >= start_date)
    if end_date:
        query = query.filter(Document.created_at <= end_date)

    if search_query:
        term = f"%{search_query.strip()}%"
        query = query.outerjoin(DocumentField).filter(
            or_(
                Document.filename.ilike(term),
                Document.type.ilike(term),
                DocumentField.value.ilike(term),
            )
        ).distinct()

    total_count = query.count()

    # Sorting
    sort_col = getattr(Document, sort_by, Document.created_at)
    order_func = desc if sort_order.lower() == "desc" else lambda c: c
    query = query.order_by(order_func(sort_col))

    # Pagination
    offset = max(0, (page - 1) * page_size)
    items = query.offset(offset).limit(page_size).all()
    return items, total_count


def get_dashboard_metrics(session: Session) -> Dict[str, Any]:
    """Aggregate statistics for documents, statuses, and accuracy metrics."""
    total_docs = session.query(func.count(Document.id)).scalar() or 0
    status_counts = dict(
        session.query(Document.status, func.count(Document.id))
        .group_by(Document.status)
        .all()
    )
    type_counts = dict(
        session.query(Document.type, func.count(Document.id))
        .group_by(Document.type)
        .all()
    )

    edited_count = (
        session.query(func.count(Document.id))
        .filter(Document.is_edited.is_(True))
        .scalar()
        or 0
    )
    unedited_count = total_docs - edited_count
    accuracy_rate = (
        (unedited_count / total_docs * 100.0) if total_docs > 0 else 100.0
    )

    # Average field confidence
    avg_confidence = (
        session.query(func.avg(DocumentField.confidence)).scalar() or 0.0
    )

    return {
        "total_documents": total_docs,
        "status_counts": {
            DocumentStatus.PROCESSED.value: status_counts.get(
                DocumentStatus.PROCESSED.value, 0
            ),
            DocumentStatus.PENDING.value: status_counts.get(
                DocumentStatus.PENDING.value, 0
            ),
            DocumentStatus.REJECTED.value: status_counts.get(
                DocumentStatus.REJECTED.value, 0
            ),
        },
        "type_counts": type_counts,
        "edited_count": edited_count,
        "unedited_count": unedited_count,
        "accuracy_rate": round(accuracy_rate, 2),
        "average_confidence": round(float(avg_confidence) * 100.0, 1),
    }
