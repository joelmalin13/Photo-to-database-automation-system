"""Unit tests for Pydantic models and field-level validation rules.

Validates schema contracts, required fields checking, and confidence scores.
"""

from __future__ import annotations

import pytest

from core.validators import (
    ExtractionResult,
    GenericTableSchema,
    ReceiptInvoiceSchema,
    StudentIDSchema,
    validate_extracted_fields,
)


def test_receipt_invoice_schema() -> None:
    """Validate valid instantiation of ReceiptInvoiceSchema."""
    model = ReceiptInvoiceSchema(
        vendor_name="Acme Market",
        total_amount=19.99,
        date="2024-10-15",
    )
    assert model.vendor_name == "Acme Market"
    assert model.total_amount == 19.99


def test_student_id_schema() -> None:
    """Validate valid instantiation of StudentIDSchema."""
    model = StudentIDSchema(
        full_name="Sarah Jenkins",
        id_number="STU-992",
        institution="City College",
    )
    assert model.full_name == "Sarah Jenkins"
    assert model.institution == "City College"


def test_generic_table_schema() -> None:
    """Validate valid instantiation of GenericTableSchema."""
    model = GenericTableSchema(
        table_title="Inventory Q3",
        total_rows=12,
    )
    assert model.table_title == "Inventory Q3"
    assert model.total_rows == 12


def test_validate_extracted_fields_missing_required() -> None:
    """Ensure missing required fields drop confidence to 0.0 and produce warnings."""
    schema_def = {
        "fields": [
            {"key": "vendor_name", "label": "Vendor", "required": True, "type": "string"},
            {"key": "total_amount", "label": "Total", "required": True, "type": "float"},
        ]
    }
    raw_fields = {"vendor_name": "Store"}  # total_amount missing
    raw_conf = {"vendor_name": 0.9}

    val_fields, confidences, warnings = validate_extracted_fields(
        "receipt_invoice", raw_fields, raw_conf, schema_def
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
        "receipt_invoice", raw_fields, raw_conf, schema_def
    )

    assert confidences["total_amount"] <= 0.4
    assert len(warnings) > 0
