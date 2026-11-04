"""Data normalization utilities for dates, monetary values, and text strings.

Transforms varied raw OCR and LLM outputs into standardized representations
(e.g., ISO-8601 dates, clean float numbers, trimmed text).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from dateutil import parser as date_parser

from config.settings import logger


def clean_text(value: Any) -> str:
    """Trim whitespace and collapse redundant spaces from string value."""
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def parse_date_to_iso(value: Any) -> Optional[str]:
    """Parse ambiguous date string and convert to ISO-8601 (YYYY-MM-DD).

    Args:
        value: Input date representation (e.g. '04/12/2024', 'Oct 15 2023').

    Returns:
        Optional[str]: Normalized YYYY-MM-DD string, or None if unparseable.
    """
    if not value:
        return None
    cleaned = clean_text(value)
    # Fast regex match for already-ISO dates
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
        return cleaned

    try:
        # Use dateutil parser with fuzzy matching
        parsed_dt = date_parser.parse(cleaned, fuzzy=True, dayfirst=False)
        return parsed_dt.strftime("%Y-%m-%d")
    except Exception as exc:
        logger.debug("Failed parsing date '%s': %s", cleaned, exc)
        return None


def parse_float_amount(value: Any) -> Optional[float]:
    """Convert raw monetary or decimal strings to clean floating point numbers.

    Handles currency symbols, comma/dot thousand separators, and negative amounts.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(round(value, 2))

    cleaned = clean_text(value)
    cleaned = re.sub(r"(?i)inr", "", cleaned)
    # Remove currency symbols and non-numeric chars except . , - +
    cleaned = re.sub(r"[^\d.,\-+]", "", cleaned)
    if not cleaned:
        return None

    # Handle European decimal notation vs thousand separators
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." not in cleaned:
        if re.search(r",\d{3}$", cleaned):
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(",", ".")

    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def parse_integer(value: Any) -> Optional[int]:
    """Extract integer value from raw text or numeric representation."""
    if value is None:
        return None
    cleaned = re.sub(r"[^\d\-+]", "", str(value))
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def normalize_fields(
    raw_fields: Dict[str, Any], schema_fields: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Normalize extracted dictionary values based on schema definitions."""
    type_map = {f["key"]: f.get("type", "string") for f in schema_fields}
    normalized: Dict[str, Any] = {}

    for key, val in raw_fields.items():
        field_type = type_map.get(key, "string")
        if field_type == "date":
            normalized[key] = parse_date_to_iso(val)
        elif field_type == "float":
            normalized[key] = parse_float_amount(val)
        elif field_type == "integer":
            normalized[key] = parse_integer(val)
        else:
            normalized[key] = clean_text(val) if val is not None else None

    return normalized
