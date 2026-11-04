"""Tests for the Ask Your Receipts natural language query service (Slide 6 #6)."""

from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.services.ask_receipts_service import AskReceiptsService
from db.models import Base, Document, Receipt


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionClass = sessionmaker(bind=engine)
    session = SessionClass()

    # Seed with ABC MART demo receipt
    r1 = Receipt(
        shop_name="ABC MART",
        date=date(2026, 11, 3),
        total_amount=1250.00,
        phone="9876543210",
        email="abcmart@gmail.com",
        pincode="580001",
        category="Grocery",
        ocr_confidence=0.85,
        subtotal=1250.00,
        tax_amount=0.00,
    )
    r2 = Receipt(
        shop_name="City Book Depot",
        date=date(2026, 11, 10),
        total_amount=450.00,
        phone="9123456780",
        email="books@city.com",
        pincode="580020",
        category="Stationery",
        ocr_confidence=0.92,
        subtotal=450.00,
        tax_amount=0.00,
    )
    session.add_all([r1, r2])
    session.commit()

    yield session
    session.close()


def test_ask_total_spent_at_shop_in_month(memory_db: Session):
    service = AskReceiptsService(memory_db)
    res = service.query("total spent at ABC MART in November")
    assert res["count"] == 1
    assert res["total"] == 1250.00
    assert "ABC MART" in res["answer"]
    assert "1,250" in res["answer"]


def test_ask_highest_expense(memory_db: Session):
    service = AskReceiptsService(memory_db)
    res = service.query("What was my highest expense?")
    assert res["total"] == 1250.00
    assert "ABC MART" in res["answer"]


def test_ask_category_spend(memory_db: Session):
    service = AskReceiptsService(memory_db)
    res = service.query("How much did I spend on Groceries?")
    assert res["total"] == 1250.00
    assert "Grocery" in res["answer"]


def test_ask_receipts_above_threshold(memory_db: Session):
    service = AskReceiptsService(memory_db)
    res = service.query("Show receipts above 1000")
    assert res["count"] == 1
    assert res["total"] == 1250.00


def test_ask_receipt_count(memory_db: Session):
    service = AskReceiptsService(memory_db)
    res = service.query("How many receipts were uploaded?")
    assert res["count"] == 2
    assert "2 confirmed" in res["answer"]
