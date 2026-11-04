"""Unit tests for Pydantic models and field-level validation rules.

Validates schema contracts, required fields checking, and confidence scores
for Receipts, Student Marksheets, and Business Cards.
"""

from __future__ import annotations

import pytest

from core.validators import (
    BusinessCardSchema,
    ExtractionResult,
    ReceiptSchema,
    StudentMarksheetSchema,
    validate_extracted_fields,
)


def test_receipt_schema() -> None:
    """Validate valid instantiation of ReceiptSchema."""
    model = ReceiptSchema(
        shop_name="Acme Market",
        total_amount=19.99,
        date="2024-10-15",
    )
    assert model.shop_name == "Acme Market"
    assert model.total_amount == 19.99


def test_student_marksheet_schema() -> None:
    """Validate valid instantiation of StudentMarksheetSchema."""
    model = StudentMarksheetSchema(
        name="Sarah Jenkins",
        usn="1MS21CS001",
        college="City Engineering College",
        total_marks=580.0,
        percentage=85.5,
    )
    assert model.name == "Sarah Jenkins"
    assert model.usn == "1MS21CS001"
    assert model.result == "PASS"


def test_business_card_schema() -> None:
    """Validate valid instantiation of BusinessCardSchema."""
    model = BusinessCardSchema(
        person_name="John Doe",
        designation="Software Architect",
        company_name="Tech Corp",
        email="john@techcorp.com",
    )
    assert model.person_name == "John Doe"
    assert model.designation == "Software Architect"


def test_validate_extracted_fields_missing_required() -> None:
    """Ensure missing required fields drop confidence to 0.0 and produce warnings."""
    schema_def = {
        "fields": [
            {"key": "shop_name", "label": "Shop Name", "required": True, "type": "string"},
            {"key": "total_amount", "label": "Total", "required": True, "type": "float"},
        ]
    }
    raw_fields = {"shop_name": "Store"}  # total_amount missing
    raw_conf = {"shop_name": 0.9}

    val_fields, confidences, warnings = validate_extracted_fields(
        "receipts", raw_fields, raw_conf, schema_def
    )

    assert confidences["total_amount"] == 0.0
    assert any("Total" in w for w in warnings)


def test_validate_extracted_fields_type_mismatch() -> None:
    """Ensure non-numeric value for float field penalizes confidence."""
    schema_def = {
        "fields": [
            {"key": "total_amount", "label": "Total", "required": False, "type": "float"}
        ]
    }
    raw_fields = {"total_amount": "not_a_number"}
    raw_conf = {"total_amount": 0.9}

    _, confidences, warnings = validate_extracted_fields(
        "receipts", raw_fields, raw_conf, schema_def
    )

    assert confidences["total_amount"] <= 0.4
    assert len(warnings) > 0
