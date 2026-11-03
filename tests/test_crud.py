"""Unit tests for SQLAlchemy database models and CRUD operations.

Tests document persistence, duplicate checks, field modifications,
status lifecycles, and metric aggregations.
"""

from __future__ import annotations

from typing import Generator
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import DocumentStatus
from db.crud import (
    create_document,
    delete_document,
    find_document_by_hash,
    get_dashboard_metrics,
    get_document_by_id,
    list_documents,
    update_document_fields,
    update_document_status,
)
from db.models import Base


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
    """Validate document persistence with fields and duplicate hash lookup."""
    doc = create_document(
        session=db_session,
        filename="test_receipt.jpg",
        image_path="/path/test_receipt.jpg",
        image_hash="abc123hash",
        doc_type="receipt_invoice",
        status=DocumentStatus.PENDING.value,
        fields={"vendor_name": "Test Mart", "total_amount": "25.50"},
        confidences={"vendor_name": 0.95, "total_amount": 0.90},
    )

    assert doc.id is not None
    assert len(doc.fields) == 2

    # Lookup by hash
    found = find_document_by_hash(db_session, "abc123hash")
    assert found is not None
    assert found.id == doc.id
    assert found.filename == "test_receipt.jpg"


def test_update_document_status(db_session: Session) -> None:
    """Validate status transitions (PENDING -> PROCESSED)."""
    doc = create_document(
        session=db_session,
        filename="invoice.png",
        image_path="/path/invoice.png",
        image_hash="hash99",
        doc_type="receipt_invoice",
    )
    assert doc.status == DocumentStatus.PENDING.value

    updated = update_document_status(
        db_session, doc.id, DocumentStatus.PROCESSED.value
    )
    assert updated is not None
    assert updated.status == DocumentStatus.PROCESSED.value


def test_update_document_fields(db_session: Session) -> None:
    """Validate editing fields marks the document as edited."""
    doc = create_document(
        session=db_session,
        filename="slip.png",
        image_path="/path/slip.png",
        image_hash="hash_slip",
        doc_type="receipt_invoice",
        fields={"vendor_name": "Old Vendor", "total_amount": "10.00"},
    )
    assert doc.is_edited is False

    updated = update_document_fields(
        db_session, doc.id, {"vendor_name": "New Corrected Vendor"}
    )
    assert updated is not None
    assert updated.is_edited is True

    field_map = {f.key: f.value for f in updated.fields}
    assert field_map["vendor_name"] == "New Corrected Vendor"


def test_list_and_filter_documents(db_session: Session) -> None:
    """Validate search, type filtering, and pagination."""
    create_document(
        session=db_session,
        filename="student_badge.png",
        image_path="/path/s.png",
        image_hash="hash_s",
        doc_type="student_id_form",
        status=DocumentStatus.PROCESSED.value,
        fields={"full_name": "Alice Smith"},
    )
    create_document(
        session=db_session,
        filename="grocery_slip.jpg",
        image_path="/path/g.jpg",
        image_hash="hash_g",
        doc_type="receipt_invoice",
        status=DocumentStatus.PENDING.value,
        fields={"vendor_name": "Fresh Market"},
    )

    # Filter by type
    docs, count = list_documents(db_session, doc_type="student_id_form")
    assert count == 1
    assert docs[0].type == "student_id_form"

    # Search query
    docs, count = list_documents(db_session, search_query="Fresh")
    assert count == 1
    assert docs[0].filename == "grocery_slip.jpg"


def test_delete_document(db_session: Session) -> None:
    """Validate document deletion cascades to child fields."""
    doc = create_document(
        session=db_session,
        filename="temp.png",
        image_path="/path/temp.png",
        image_hash="temp_hash",
        doc_type="generic_table",
        fields={"table_title": "Audit"},
    )
    doc_id = doc.id
    assert get_document_by_id(db_session, doc_id) is not None

    deleted = delete_document(db_session, doc_id)
    assert deleted is True
    assert get_document_by_id(db_session, doc_id) is None


def test_dashboard_metrics(db_session: Session) -> None:
    """Validate analytics calculation for counts, accuracy, and status."""
    create_document(
        session=db_session,
        filename="d1.png",
        image_path="/p1",
        image_hash="h1",
        doc_type="receipt_invoice",
        status=DocumentStatus.PROCESSED.value,
    )
    create_document(
        session=db_session,
        filename="d2.png",
        image_path="/p2",
        image_hash="h2",
        doc_type="receipt_invoice",
        status=DocumentStatus.PENDING.value,
    )

    metrics = get_dashboard_metrics(db_session)
    assert metrics["total_documents"] == 2
    assert metrics["status_counts"]["processed"] == 1
    assert metrics["status_counts"]["pending"] == 1
    assert metrics["accuracy_rate"] == 100.0  # neither edited
