"""Pydantic models and field-level validation logic for SnapBase documents.

Enforces schema contracts, validates required attributes, verifies value
types, and computes adjusted per-field confidence scores.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from config.settings import CONFIDENCE_THRESHOLD, logger


class ExtractionResult(BaseModel):
    """Container for the raw and structured output of an extraction engine."""

    doc_type: str
    fields: Dict[str, Any] = Field(default_factory=dict)
    confidences: Dict[str, float] = Field(default_factory=dict)
    line_items: List[Dict[str, Any]] = Field(default_factory=list)
    raw_text: str = ""
    engine_used: str = "unknown"


class ReceiptInvoiceSchema(BaseModel):
    """Schema model for commercial receipts and purchase invoices."""

    vendor_name: str
    invoice_number: Optional[str] = None
    date: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    payment_method: Optional[str] = None


class StudentIDSchema(BaseModel):
    """Schema model for student registration and identification cards."""

    full_name: str
    id_number: str
    date_of_birth: Optional[str] = None
    institution: str
    valid_until: Optional[str] = None
    blood_group: Optional[str] = None


class GenericTableSchema(BaseModel):
    """Schema model for generic tabular documents and schedules."""

    table_title: str
    record_date: Optional[str] = None
    total_rows: Optional[int] = None
    summary_notes: Optional[str] = None


TYPE_MODEL_MAP = {
    "receipt_invoice": ReceiptInvoiceSchema,
    "student_id_form": StudentIDSchema,
    "generic_table": GenericTableSchema,
}


def validate_extracted_fields(
    doc_type: str,
    normalized_fields: Dict[str, Any],
    raw_confidences: Dict[str, float],
    schema_def: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, float], List[str]]:
    """Validate normalized fields against schema rules and compute field confidences.

    Args:
        doc_type: Document classification key.
        normalized_fields: Normalized field key-value pairs.
        raw_confidences: Initial engine-provided confidence scores.
        schema_def: Loaded schema definition for this document type.

    Returns:
        Tuple[Dict[str, Any], Dict[str, float], List[str]]:
            (validated_fields, final_confidences, validation_warnings)
    """
    field_defs = schema_def.get("fields", [])
    validated: Dict[str, Any] = dict(normalized_fields)
    confidences: Dict[str, float] = dict(raw_confidences)
    warnings: List[str] = []

    for f_def in field_defs:
        key = f_def["key"]
        val = validated.get(key)
        is_required = f_def.get("required", False)

        # Baseline confidence if omitted by engine
        if key not in confidences:
            confidences[key] = 0.85 if val is not None else 0.0

        # Check required fields
        if is_required and (val is None or str(val).strip() == ""):
            confidences[key] = 0.0
            warnings.append(f"Required field '{f_def.get('label', key)}' is missing.")
        elif val is not None:
            # Type checks
            expected_type = f_def.get("type", "string")
            if expected_type in ("float", "integer") and not isinstance(
                val, (int, float)
            ):
                confidences[key] = min(confidences[key], 0.4)
                warnings.append(
                    f"Field '{key}' expected numeric value, got '{val}'"
                )

    # Low confidence alerts
    low_conf_keys = [
        k for k, score in confidences.items() if score < CONFIDENCE_THRESHOLD
    ]
    if low_conf_keys:
        logger.warning(
            "Document %s has low-confidence fields: %s",
            doc_type,
            low_conf_keys,
        )

    return validated, confidences, warnings
