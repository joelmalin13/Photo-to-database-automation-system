"""Parameterized database CRUD operations and lifecycle management.

Enforces strict domain rules:
- Duplicate prevention via unique image SHA-256 hash.
- Audit logging of all actions into processing_history.
- Confirmed records promotion ONLY upon human/verified approval.
"""

from __future__ import annotations

from datetime import date, datetime
import math
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from config.settings import DocumentCategory, DocumentStatus, logger
from db.models import (
    BusinessCard,
    Document,
    Mark,
    ProcessingHistory,
    Receipt,
    ReceiptItem,
    Student,
)


def log_processing_step(
    session: Session,
    document_id: int,
    step_name: str,
    status: str = "success",
    details: Optional[str] = None,
    execution_time_ms: int = 0,
) -> ProcessingHistory:
    """Log an execution step or error event to processing_history."""
    history = ProcessingHistory(
        document_id=document_id,
        step_name=step_name,
        status=status,
        details=details,
        execution_time_ms=execution_time_ms,
    )
    session.add(history)
    return history


def create_document(
    session: Session,
    filename: str,
    image_path: str,
    image_hash: str,
    category: str = DocumentCategory.RECEIPTS.value,
    ocr_text: Optional[str] = None,
    ocr_confidence: float = 0.0,
    status: str = DocumentStatus.PROCESSED.value,
    raw_fields: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    execution_time_ms: int = 0,
) -> Document:
    """Create a new document entity and record initial processing history."""
    doc = Document(
        user_id=user_id,
        filename=filename,
        image_path=image_path,
        image_hash=image_hash,
        category=category,
        ocr_text=ocr_text,
        ocr_confidence=float(ocr_confidence),
        status=status,
        raw_fields_json=raw_fields or {},
    )
    session.add(doc)
    session.flush()

    log_processing_step(
        session=session,
        document_id=doc.id,
        step_name="ingestion_and_extraction",
        status="success" if status != DocumentStatus.FAILED.value else "failed",
        details=f"Extracted category: {category}, confidence: {ocr_confidence:.2f}",
        execution_time_ms=execution_time_ms,
    )
    return doc


def get_document_by_id(session: Session, doc_id: int) -> Optional[Document]:
    """Retrieve single document with confirmed child relations pre-loaded."""
    stmt = (
        select(Document)
        .options(
            joinedload(Document.receipt).joinedload(Receipt.items),
            joinedload(Document.student).joinedload(Student.marks),
            joinedload(Document.business_card),
            joinedload(Document.history),
        )
        .where(Document.id == doc_id)
    )
    return session.scalar(stmt)


def find_document_by_hash(session: Session, image_hash: str) -> Optional[Document]:
    """Look up an existing document by unique SHA-256 hash."""
    stmt = select(Document).where(Document.image_hash == image_hash)
    return session.scalar(stmt)


def update_document_status(
    session: Session, doc_id: int, new_status: str, note: Optional[str] = None
) -> Optional[Document]:
    """Update document lifecycle status with history log."""
    doc = get_document_by_id(session, doc_id)
    if not doc:
        return None
    old_status = doc.status
    doc.status = new_status
    session.flush()

    hist = log_processing_step(
        session=session,
        document_id=doc.id,
        step_name="status_transition",
        status=new_status,
        details=f"Status transitioned from {old_status} to {new_status}. {note or ''}".strip(),
    )
    doc.history.append(hist)
    session.flush()
    return doc


def update_document_raw_fields(
    session: Session, doc_id: int, updated_fields: Dict[str, Any]
) -> Optional[Document]:
    """Update raw extracted fields stored in the document JSON column."""
    doc = get_document_by_id(session, doc_id)
    if not doc:
        return None
    current = doc.raw_fields_json or {}
    current["fields"] = updated_fields
    doc.raw_fields_json = dict(current)
    session.flush()

    log_processing_step(
        session=session,
        document_id=doc.id,
        step_name="field_edit",
        status="success",
        details="Extracted fields edited via review interface.",
    )
    return doc


def delete_document(session: Session, doc_id: int) -> bool:
    """Delete document entity and all cascading children."""
    doc = session.get(Document, doc_id)
    if not doc:
        return False
    session.delete(doc)
    session.flush()
    return True


def list_documents(
    session: Session,
    category: Optional[str] = None,
    status: Optional[str] = None,
    search_query: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 10,
) -> Tuple[List[Document], int]:
    """Parameterized search, filtering, and pagination for document records."""
    stmt = select(Document).options(
        joinedload(Document.receipt),
        joinedload(Document.student),
        joinedload(Document.business_card),
    )

    # Normalize category filters
    if category and category != "all":
        if category in ("receipt_invoice", "receipts"):
            stmt = stmt.where(Document.category.in_(["receipts", "receipt_invoice"]))
        elif category in ("student_marksheet", "students", "student_id_form"):
            stmt = stmt.where(Document.category.in_(["students", "student_marksheet", "student_id_form"]))
        elif category in ("business_card", "business_cards"):
            stmt = stmt.where(Document.category.in_(["business_cards", "business_card"]))
        else:
            stmt = stmt.where(Document.category == category)

    if status and status != "all":
        stmt = stmt.where(Document.status == status)

    if search_query:
        pattern = f"%{search_query.strip()}%"
        stmt = stmt.where(
            or_(
                Document.filename.ilike(pattern),
                Document.ocr_text.ilike(pattern),
                Document.category.ilike(pattern),
            )
        )

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.scalar(count_stmt) or 0

    # Sort
    sort_col = getattr(Document, sort_by, Document.created_at)
    stmt = stmt.order_by(desc(sort_col) if sort_order.lower() == "desc" else sort_col)

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    results = list(session.scalars(stmt).unique())
    return results, total


def promote_to_confirmed_record(
    session: Session,
    doc_id: int,
    verified_fields: Dict[str, Any],
    items: Optional[List[Dict[str, Any]]] = None,
) -> Document:
    """Promote verified extracted data into the official normalized business tables.

    Rule: Never save unverified OCR output as confirmed data. Only approved records
    populate receipts, students, or business_cards tables.
    """
    doc = get_document_by_id(session, doc_id)
    if not doc:
        raise ValueError(f"Document #{doc_id} not found.")

    category = doc.category.lower()

    # 1. Receipts / Invoices Promotion
    if category in ("receipts", "receipt_invoice"):
        raw_date = verified_fields.get("date")
        parsed_date = None
        if raw_date:
            try:
                parsed_date = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
            except Exception:
                parsed_date = None

        receipt = doc.receipt
        if not receipt:
            receipt = Receipt(document_id=doc.id)
            doc.receipt = receipt
            session.add(receipt)

        receipt.shop_name = str(verified_fields.get("shop_name") or verified_fields.get("vendor_name") or "Unknown Merchant")
        receipt.receipt_number = str(verified_fields.get("receipt_number") or verified_fields.get("invoice_number") or "")
        receipt.date = parsed_date
        receipt.phone = str(verified_fields.get("phone") or "")
        receipt.subtotal = float(verified_fields.get("subtotal") or 0.0)
        receipt.tax_amount = float(verified_fields.get("tax_amount") or 0.0)
        receipt.total_amount = float(verified_fields.get("total_amount") or 0.0)

        # Update items
        if items is not None:
            receipt.items.clear()
            for it in items:
                item_name = str(it.get("item_name") or it.get("description") or "Item")
                qty = float(it.get("quantity") or 1.0)
                unit_p = float(it.get("unit_price") or 0.0)
                tot_p = float(it.get("total_price") or it.get("amount") or (qty * unit_p))
                receipt.items.append(
                    ReceiptItem(
                        item_name=item_name,
                        quantity=qty,
                        unit_price=unit_p,
                        total_price=tot_p,
                    )
                )

    # 2. Students / Marksheet Promotion
    elif category in ("students", "student_marksheet", "student_id_form"):
        student = doc.student
        if not student:
            student = Student(document_id=doc.id)
            doc.student = student
            session.add(student)

        student.name = str(verified_fields.get("name") or verified_fields.get("full_name") or "Student Name")
        student.usn = str(verified_fields.get("usn") or verified_fields.get("id_number") or "N/A")
        student.college = str(verified_fields.get("college") or verified_fields.get("institution") or "")
        student.semester = str(verified_fields.get("semester") or "")
        student.total_marks = float(verified_fields.get("total_marks") or 0.0)
        student.percentage = float(verified_fields.get("percentage") or 0.0)
        student.result = str(verified_fields.get("result") or "PASS")

        # Update marks
        if items is not None:
            student.marks.clear()
            for m in items:
                subj = str(m.get("subject_name") or m.get("subject") or "Subject")
                code = str(m.get("subject_code") or m.get("code") or "")
                obt = float(m.get("marks_obtained") or m.get("marks") or 0.0)
                max_m = float(m.get("max_marks") or 100.0)
                student.marks.append(
                    Mark(
                        subject_name=subj,
                        subject_code=code,
                        marks_obtained=obt,
                        max_marks=max_m,
                    )
                )

    # 3. Business Cards Promotion
    elif category in ("business_cards", "business_card"):
        card = doc.business_card
        if not card:
            card = BusinessCard(document_id=doc.id)
            doc.business_card = card
            session.add(card)

        card.person_name = str(verified_fields.get("person_name") or verified_fields.get("name") or "Contact")
        card.designation = str(verified_fields.get("designation") or verified_fields.get("title") or "")
        card.company_name = str(verified_fields.get("company_name") or verified_fields.get("company") or "")
        card.phone = str(verified_fields.get("phone") or "")
        card.email = str(verified_fields.get("email") or "")
        card.website = str(verified_fields.get("website") or "")
        card.address = str(verified_fields.get("address") or "")

    # Set document status to verified
    doc.status = DocumentStatus.VERIFIED.value
    # Keep raw_fields in sync
    raw = doc.raw_fields_json or {}
    raw["fields"] = verified_fields
    if items is not None:
        raw["line_items"] = items
    doc.raw_fields_json = dict(raw)

    session.flush()

    log_processing_step(
        session=session,
        document_id=doc.id,
        step_name="human_verification",
        status="verified",
        details=f"Promoted to official confirmed table: {category}",
    )
    return doc


def get_dashboard_metrics(session: Session) -> Dict[str, Any]:
    """Retrieve operational dashboard counts and status splits."""
    total_docs = session.scalar(select(func.count(Document.id))) or 0
    verified_docs = session.scalar(
        select(func.count(Document.id)).where(Document.status == DocumentStatus.VERIFIED.value)
    ) or 0
    processed_docs = session.scalar(
        select(func.count(Document.id)).where(Document.status == DocumentStatus.PROCESSED.value)
    ) or 0
    rejected_docs = session.scalar(
        select(func.count(Document.id)).where(Document.status == DocumentStatus.REJECTED.value)
    ) or 0
    failed_docs = session.scalar(
        select(func.count(Document.id)).where(Document.status == DocumentStatus.FAILED.value)
    ) or 0

    avg_conf = session.scalar(select(func.avg(Document.ocr_confidence))) or 0.0

    # Category counts
    cat_rows = (
        session.query(Document.category, func.count(Document.id))
        .group_by(Document.category)
        .all()
    )
    cat_counts = {r[0]: r[1] for r in cat_rows}

    return {
        "total_documents": total_docs,
        "verified_count": verified_docs,
        "pending_review": processed_docs,
        "rejected_count": rejected_docs,
        "failed_count": failed_docs,
        "average_confidence": round(float(avg_conf), 2),
        "status_counts": {
            "verified": verified_docs,
            "processed": processed_docs,
            "pending": processed_docs,  # Backwards compatibility alias
            "rejected": rejected_docs,
            "failed": failed_docs,
        },
        "category_counts": cat_counts,
        "type_counts": cat_counts,  # Backwards compatibility alias
    }


def get_analytics_data(session: Session) -> Dict[str, Any]:
    """Aggregate comprehensive analytics metrics for Chart.js visualizations.

    Includes:
    - category distribution
    - monthly trend
    - success vs failure
    - receipt expenses
    - top shops by spend
    - student marks comparison
    """
    metrics = get_dashboard_metrics(session)

    # 1. Monthly trend
    dialect_name = ""
    try:
        bind = session.get_bind()
        if bind and bind.dialect:
            dialect_name = bind.dialect.name
    except Exception:
        dialect_name = "sqlite"

    month_col = (
        func.strftime("%Y-%m", Document.created_at)
        if "sqlite" in dialect_name
        else func.date_format(Document.created_at, "%Y-%m")
    )
    monthly_rows = (
        session.query(
            month_col.label("month_str"),
            func.count(Document.id).label("doc_count"),
        )
        .group_by(month_col)
        .order_by(month_col)
        .limit(12)
        .all()
    )
    monthly_trend = {
        "labels": [str(r[0]) for r in monthly_rows] if monthly_rows else ["Current Month"],
        "values": [int(r[1]) for r in monthly_rows] if monthly_rows else [metrics["total_documents"]],
    }

    # 2. Receipt expenses & top shops by spend
    receipt_rows = (
        session.query(Receipt.shop_name, func.sum(Receipt.total_amount), func.count(Receipt.id))
        .group_by(Receipt.shop_name)
        .order_by(desc(func.sum(Receipt.total_amount)))
        .limit(6)
        .all()
    )
    top_shops = {
        "labels": [r[0] for r in receipt_rows],
        "expenses": [round(float(r[1]), 2) for r in receipt_rows],
        "counts": [r[2] for r in receipt_rows],
    }

    # Total confirmed expenses
    total_spend = session.scalar(select(func.sum(Receipt.total_amount))) or 0.0

    # 3. Student performance comparison
    student_rows = (
        session.query(Student.name, Student.percentage, Student.result)
        .order_by(desc(Student.percentage))
        .limit(6)
        .all()
    )
    student_comparison = {
        "labels": [r[0] for r in student_rows],
        "percentages": [round(float(r[1]), 1) for r in student_rows],
        "results": [r[2] for r in student_rows],
    }

    # 4. Success vs Failure
    success_count = metrics["verified_count"] + metrics["pending_review"]
    failure_count = metrics["rejected_count"] + metrics["failed_count"]

    return {
        "metrics": metrics,
        "total_spend": round(float(total_spend), 2),
        "monthly_trend": monthly_trend,
        "top_shops": top_shops,
        "student_comparison": student_comparison,
        "success_vs_failure": {
            "success": success_count,
            "failure": failure_count,
        },
    }
