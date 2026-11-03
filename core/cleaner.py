"""Data cleaning, sanitization, and normalization pipeline using Pandas.

Implements Section 6 specifications:
- Trim whitespace from string entries
- Standardise dates to ISO 8601 (YYYY-MM-DD)
- Standardise telephone and mobile formats (+Country-Code format)
- Validate and sanitize email addresses
- Parse and validate monetary amounts
- Handle missing values and detect suspicious anomalies
- Generate preview DataFrames before database persistence
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from dateutil import parser as date_parser

from config.settings import logger


def trim_whitespace(val: Any) -> Any:
    """Trim leading, trailing, and excessive internal whitespace."""
    if isinstance(val, str):
        cleaned = re.sub(r"\s+", " ", val).strip()
        return cleaned if cleaned else None
    return val


def standardize_date(val: Any) -> Optional[str]:
    """Parse multiple date string representations into standard ISO 8601 YYYY-MM-DD."""
    if not val:
        return None
    s = str(val).strip()
    try:
        dt = date_parser.parse(s, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        # Fallback regex for DD/MM/YYYY or YYYY-MM-DD
        m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        m2 = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", s)
        if m2:
            yr = m2.group(3)
            if len(yr) == 2:
                yr = f"20{yr}"
            return f"{yr}-{int(m2.group(2)):02d}-{int(m2.group(1)):02d}"
    return None


def standardize_phone(val: Any) -> Optional[str]:
    """Standardize phone string, stripping noise while preserving international prefix."""
    if not val:
        return None
    s = str(val).strip()
    digits = re.sub(r"[^\d+]", "", s)
    if len(digits) >= 7:
        if digits.startswith("+"):
            return digits
        elif len(digits) == 10:
            return f"+91-{digits[:5]}-{digits[5:]}"
        return digits
    return None


def validate_email(val: Any) -> Optional[str]:
    """Validate and lower-case email addresses."""
    if not val:
        return None
    s = str(val).strip().lower()
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if re.match(pattern, s):
        return s
    return None


def parse_monetary_amount(val: Any) -> Optional[float]:
    """Extract clean float value from currency strings."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return round(float(val), 2)
    s = str(val).strip()
    # Strip symbols ($ € £ ₹)
    s = re.sub(r"[^\d.,-]", "", s)
    if not s:
        return None

    # Handle European decimal formatting (1.250,50 -> 1250.50)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")

    try:
        return round(float(s), 2)
    except ValueError:
        return None


def clean_document_record(
    raw_fields: Dict[str, Any], category: str
) -> Tuple[Dict[str, Any], List[str]]:
    """Clean, format, and detect suspicious fields using a Pandas pipeline.

    Returns:
        Tuple[Dict[str, Any], List[str]]: (cleaned_fields_dict, list_of_suspicious_warnings)
    """
    df = pd.DataFrame([raw_fields])
    warnings: List[str] = []

    cleaned: Dict[str, Any] = {}

    for col in df.columns:
        val = df[col].iloc[0]
        trimmed = trim_whitespace(val)

        # Field specific formatting
        if col in ("date", "valid_until", "date_of_birth", "record_date"):
            std_date = standardize_date(trimmed)
            cleaned[col] = std_date
            if trimmed and not std_date:
                warnings.append(f"Suspicious unparseable date in '{col}': '{trimmed}'")

        elif col in ("phone", "mobile", "telephone"):
            std_phone = standardize_phone(trimmed)
            cleaned[col] = std_phone
            if trimmed and not std_phone:
                warnings.append(f"Suspicious incomplete phone number in '{col}': '{trimmed}'")

        elif col in ("email",):
            valid_em = validate_email(trimmed)
            cleaned[col] = valid_em
            if trimmed and not valid_em:
                warnings.append(f"Suspicious or invalid email format in '{col}': '{trimmed}'")

        elif col in ("total_amount", "tax_amount", "subtotal", "total_marks", "percentage", "unit_price", "total_price"):
            amt = parse_monetary_amount(trimmed)
            cleaned[col] = amt
            if trimmed and amt is None:
                warnings.append(f"Suspicious non-numeric value in monetary/score field '{col}': '{trimmed}'")

        else:
            cleaned[col] = trimmed

    # Category-specific sanity checks
    if category in ("receipts", "receipt_invoice"):
        total = cleaned.get("total_amount")
        subtotal = cleaned.get("subtotal")
        tax = cleaned.get("tax_amount")
        if total is not None and subtotal is not None and tax is not None:
            calc_sum = round(subtotal + tax, 2)
            if abs(calc_sum - total) > 1.0:
                warnings.append(
                    f"Arithmetic mismatch: Subtotal ({subtotal}) + Tax ({tax}) = {calc_sum} != Total ({total})"
                )

    elif category in ("students", "student_marksheet"):
        pct = cleaned.get("percentage")
        if pct is not None and (pct < 0 or pct > 100):
            warnings.append(f"Suspicious percentage out of bounds: {pct}%")

    return cleaned, warnings


def build_preview_dataframe(
    records: List[Dict[str, Any]]
) -> pd.DataFrame:
    """Build a consolidated Pandas preview table for UI display."""
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    # Fill missing values gracefully
    df = df.fillna("—")
    return df
