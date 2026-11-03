"""Unit tests for normalized SQLAlchemy database models and CRUD operations.

Tests document persistence, duplicate checks, raw field updates,
status lifecycles, confirmed record promotion (receipts, students, business cards),
and audit logging in processing_history.
"""

from __future__ import annotations

from datetime import date
from typing import Generator
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import DocumentCategory, DocumentStatus
from db.crud import (
    create_document,
    delete_document,
    find_document_by_hash,
    get_dashboard_metrics,
    get_document_by_id,
    list_documents,
    promote_to_confirmed_record,
    update_document_raw_fields,
    update_document_status,
)
from db.models import (
    Base,
    BusinessCard,
    Document,
    Mark,
    ProcessingHistory,
    Receipt,
    ReceiptItem,
    Student,
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide an isolated, clean in-memory database session for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_create_and_find_document(db_session: Session) -> None:
    """Validate document persistence and duplicate hash lookup."""
    doc = create_document(
        session=db_session,
        filename="test_receipt.jpg",
        image_path="/path/test_receipt.jpg",
        image_hash="abc123hash",
        category=DocumentCategory.RECEIPTS.value,
        ocr_text="SAMPLE RECEIPT 25.50",
        ocr_confidence=0.92,
        status=DocumentStatus.PROCESSED.value,
        raw_fields={"shop_name": "Test Mart", "total_amount": 25.50},
    )

    assert doc.id is not None
    assert doc.image_hash == "abc123hash"
    assert doc.status == DocumentStatus.PROCESSED.value

    # Lookup by hash
    found = find_document_by_hash(db_session, "abc123hash")
    assert found is not None
    assert found.id == doc.id
    assert found.filename == "test_receipt.jpg"


def test_update_document_status(db_session: Session) -> None:
    """Validate status transitions and processing history logging."""
    doc = create_document(
        session=db_session,
        filename="invoice.png",
        image_path="/path/invoice.png",
        image_hash="hash99",
        category=DocumentCategory.RECEIPTS.value,
    )
    assert doc.status == DocumentStatus.PROCESSED.value

    updated = update_document_status(
        db_session, doc.id, DocumentStatus.REJECTED.value, note="Blurry image"
    )
    assert updated is not None
    assert updated.status == DocumentStatus.REJECTED.value

    # History was logged
    history_steps = [h.step_name for h in updated.history]
    assert "status_transition" in history_steps


def test_update_document_raw_fields(db_session: Session) -> None:
    """Validate editing raw fields in JSON column."""
    doc = create_document(
        session=db_session,
        filename="slip.png",
        image_path="/path/slip.png",
        image_hash="hash_slip",
        category=DocumentCategory.RECEIPTS.value,
        raw_fields={"fields": {"shop_name": "Old Vendor", "total_amount": 10.00}},
    )

    updated = update_document_raw_fields(
        db_session, doc.id, {"shop_name": "New Corrected Vendor", "total_amount": 10.00}
    )
    assert updated is not None
    assert updated.raw_fields_json["fields"]["shop_name"] == "New Corrected Vendor"


def test_list_and_filter_documents(db_session: Session) -> None:
    """Validate category filtering, search, and pagination."""
    create_document(
        session=db_session,
        filename="student_badge.png",
        image_path="/path/s.png",
        image_hash="hash_s",
        category=DocumentCategory.STUDENTS.value,
        status=DocumentStatus.VERIFIED.value,
        ocr_text="VTU University Student Marksheet 1MS21CS001",
    )
    create_document(
        session=db_session,
        filename="grocery_slip.jpg",
        image_path="/path/g.jpg",
        image_hash="hash_g",
        category=DocumentCategory.RECEIPTS.value,
        status=DocumentStatus.PROCESSED.value,
        ocr_text="Fresh Market Grocery Receipt",
    )

    # Filter by category
    docs, count = list_documents(db_session, category="students")
    assert count == 1
    assert docs[0].category == "students"

    # Search query
    docs, count = list_documents(db_session, search_query="Fresh")
    assert count == 1
    assert docs[0].filename == "grocery_slip.jpg"


def test_unverified_ocr_is_not_confirmed(db_session: Session) -> None:
    """Ensure unverified documents do NOT populate confirmed business tables."""
    doc = create_document(
        session=db_session,
        filename="raw_ocr.png",
        image_path="/path/raw.png",
        image_hash="hash_unverified",
        category=DocumentCategory.RECEIPTS.value,
        raw_fields={"fields": {"shop_name": "Potential Shop", "total_amount": 42.0}},
    )

    # Document exists in documents table
    assert doc.id is not None
    # Confirmed tables must be empty
    assert doc.receipt is None
    assert doc.student is None
    assert doc.business_card is None


def test_promote_receipt_to_confirmed(db_session: Session) -> None:
    """Test promoting an approved receipt populates receipts and receipt_items."""
    doc = create_document(
        session=db_session,
        filename="rec.png",
        image_path="/path/rec.png",
        image_hash="hash_receipt_prom",
        category="receipts",
    )

    verified_data = {
        "shop_name": "Target Store",
        "receipt_number": "RCP-8899",
        "date": "2024-04-10",
        "phone": "555-0199",
        "subtotal": 50.0,
        "tax_amount": 4.12,
        "total_amount": 54.12,
    }
    items = [
        {"item_name": "Notebook", "quantity": 2, "price": 10.0, "amount": 20.0},
        {"item_name": "Pen Set", "quantity": 1, "price": 30.0, "amount": 30.0},
    ]

    promoted_doc = promote_to_confirmed_record(
        db_session, doc.id, verified_data, items=items
    )

    assert promoted_doc.status == DocumentStatus.VERIFIED.value
    assert promoted_doc.receipt is not None
    assert promoted_doc.receipt.shop_name == "Target Store"
    assert promoted_doc.receipt.total_amount == 54.12
    assert len(promoted_doc.receipt.items) == 2
    assert promoted_doc.receipt.items[0].item_name == "Notebook"


def test_promote_student_to_confirmed(db_session: Session) -> None:
    """Test promoting an approved marksheet populates students and marks."""
    doc = create_document(
        session=db_session,
        filename="marksheet.png",
        image_path="/path/marksheet.png",
        image_hash="hash_student_prom",
        category="students",
    )

    verified_data = {
        "name": "Jane Smith",
        "usn": "1MS21CS045",
        "college": "BMS College of Engineering",
        "semester": "6",
        "total_marks": 650.0,
        "percentage": 81.25,
        "result": "PASS",
    }
    marks = [
        {"subject_name": "Cloud Computing", "subject_code": "21CS61", "marks_obtained": 85, "max_marks": 100},
        {"subject_name": "Machine Learning", "subject_code": "21CS62", "marks_obtained": 88, "max_marks": 100},
    ]

    promoted_doc = promote_to_confirmed_record(
        db_session, doc.id, verified_data, items=marks
    )

    assert promoted_doc.status == DocumentStatus.VERIFIED.value
    assert promoted_doc.student is not None
    assert promoted_doc.student.name == "Jane Smith"
    assert promoted_doc.student.usn == "1MS21CS045"
    assert len(promoted_doc.student.marks) == 2


def test_promote_business_card_to_confirmed(db_session: Session) -> None:
    """Test promoting an approved business card populates business_cards."""
    doc = create_document(
        session=db_session,
        filename="card.png",
        image_path="/path/card.png",
        image_hash="hash_card_prom",
        category="business_cards",
    )

    verified_data = {
        "person_name": "Alice Johnson",
        "designation": "Director of Engineering",
        "company_name": "Acme Innovations",
        "email": "alice@acme.io",
        "phone": "+1-555-0987",
        "website": "https://acme.io",
        "address": "100 Market St, San Francisco, CA",
    }

    promoted_doc = promote_to_confirmed_record(db_session, doc.id, verified_data)

    assert promoted_doc.status == DocumentStatus.VERIFIED.value
    assert promoted_doc.business_card is not None
    assert promoted_doc.business_card.person_name == "Alice Johnson"
    assert promoted_doc.business_card.email == "alice@acme.io"


def test_delete_document(db_session: Session) -> None:
    """Validate document deletion cascades to child confirmed tables."""
    doc = create_document(
        session=db_session,
        filename="temp.png",
        image_path="/path/temp.png",
        image_hash="hash_temp",
        category="receipts",
    )
    promote_to_confirmed_record(
        db_session, doc.id, {"shop_name": "Temp Store", "total_amount": 10.0}
    )

    doc_id = doc.id
    assert delete_document(db_session, doc_id) is True
    assert get_document_by_id(db_session, doc_id) is None
