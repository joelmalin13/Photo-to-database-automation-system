"""Unit tests for SnapBase normalization functions.

Tests date parsing, monetary float conversions, text trimming, and schema normalization.
"""

from __future__ import annotations

import pytest

from core.normalize import (
    clean_text,
    normalize_fields,
    parse_date_to_iso,
    parse_float_amount,
    parse_integer,
)


@pytest.mark.parametrize(
    "raw_input,expected",
    [
        ("2024-10-15", "2024-10-15"),
        ("15/10/2024", "2024-10-15"),
        ("10/15/2024", "2024-10-15"),
        ("October 15, 2024", "2024-10-15"),
        ("15-10-2024", "2024-10-15"),
        ("", None),
        (None, None),
        ("not-a-date", None),
    ],
)
def test_parse_date_to_iso(raw_input: str | None, expected: str | None) -> None:
    """Validate conversion of diverse date formats to ISO-8601 string."""
    assert parse_date_to_iso(raw_input) == expected


@pytest.mark.parametrize(
    "raw_input,expected",
    [
        ("$18.84", 18.84),
        ("€ 1,250.50", 1250.50),
        ("1.250,50", 1250.50),
        ("9.99", 9.99),
        ("-45.00", -45.00),
        ("Free", None),
        (None, None),
        (100, 100.0),
    ],
)
def test_parse_float_amount(raw_input: str | None, expected: float | None) -> None:
    """Validate numeric conversion and currency symbol stripping."""
    assert parse_float_amount(raw_input) == expected


@pytest.mark.parametrize(
    "raw_input,expected",
    [
        ("  Hello   World  \n", "Hello World"),
        ("SingleWord", "SingleWord"),
        ("", ""),
        (None, ""),
    ],
)
def test_clean_text(raw_input: str | None, expected: str) -> None:
    """Validate whitespace stripping and collapse."""
    assert clean_text(raw_input) == expected


def test_parse_integer() -> None:
    """Validate integer string conversion."""
    assert parse_integer("42") == 42
    assert parse_integer("Item count: 120") == 120
    assert parse_integer("invalid") is None
    assert parse_integer(None) is None


def test_normalize_fields() -> None:
    """Validate end-to-end field normalization against schema specs."""
    schema_fields = [
        {"key": "vendor_name", "type": "string"},
        {"key": "date", "type": "date"},
        {"key": "total_amount", "type": "float"},
        {"key": "row_count", "type": "integer"},
    ]
    raw = {
        "vendor_name": "  ACME Store  ",
        "date": "2024-11-05",
        "total_amount": "$45.99",
        "row_count": "15 items",
    }
    result = normalize_fields(raw, schema_fields)
    assert result["vendor_name"] == "ACME Store"
    assert result["date"] == "2024-11-05"
    assert result["total_amount"] == 45.99
    assert result["row_count"] == 15
