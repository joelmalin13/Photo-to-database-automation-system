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
    """Standardize phone string, preserving clean 10-digit mobile number."""
    if not val:
        return None
    s = str(val).strip()
    digits = re.sub(r"[^\d]", "", s)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) == 10:
        return digits
    elif len(digits) >= 7:
        return digits
    return None


def validate_email(val: Any) -> Optional[str]:
    """Validate and clean email addresses, auto-correcting OCR missing dots."""
    if not val:
        return None
    s = str(val).strip().lower()
    # Correct OCR missed dot before common domains (e.g. gmailcom -> gmail.com)
    s = re.sub(r"@([a-zA-Z0-9-]+)(com|org|net|in|edu|gov)$", r"@\1.\2", s)
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if re.match(pattern, s):
        return s
    return None


def standardize_pincode(val: Any) -> Optional[str]:
    """Standardize 6-digit postal PIN code."""
    if not val:
        return None
    digits = re.sub(r"[^\d]", "", str(val))
    if len(digits) == 6:
        return digits
    return digits if digits else None


def auto_categorize_receipt(shop_name: str, raw_text: str = "", items: Optional[List[Dict[str, Any]]] = None) -> str:
    """Classify receipt category based on shop name, line items, and raw text keywords (Slide 6 #3)."""
    combined = f"{shop_name} {raw_text}".lower()
    if items:
        for it in items:
            combined += f" {it.get('item_name', '')} {it.get('description', '')}".lower()

    if any(k in combined for k in ["mart", "grocery", "supermarket", "provisions", "rice", "atta", "oil", "dal", "butter", "milk", "vegetable", "fruit", "food", "flour"]):
        return "Grocery"
    if any(k in combined for k in ["restaurant", "cafe", "coffee", "bistro", "pizza", "burger", "hotel", "dine", "dining", "bar", "bakery", "kitchen"]):
        return "Restaurant"
    if any(k in combined for k in ["stationery", "book", "pen", "paper", "print", "xerox", "notebook", "office"]):
        return "Stationery"
    if any(k in combined for k in ["pharmacy", "medical", "chemist", "pharma", "medicine", "tablet", "syrup"]):
        return "Pharmacy"
    if any(k in combined for k in ["electronics", "digital", "mobile", "computer", "cables", "gadget", "charger"]):
        return "Electronics"
    if any(k in combined for k in ["clothing", "apparel", "wear", "garments", "textiles", "fashion", "dress", "shirt"]):
        return "Clothing"
    return "General Store"


def parse_monetary_amount(val: Any) -> Optional[float]:
    """Extract clean float value from currency strings."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return round(float(val), 2)
    s = str(val).strip()
    # Strip currency labels and non-numeric characters
    s = re.sub(r"(?i)inr", "", s)
    s = re.sub(r"[^\d.,-]", "", s)
    if not s:
        return None

    # Handle European decimal formatting vs thousand commas
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s and "." not in s:
        # If comma is followed by 3 digits (e.g. 1,250), it is a thousands separator
        if re.search(r",\d{3}$", s):
            s = s.replace(",", "")
        else:
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

        elif col in ("pincode", "postal_code", "pin"):
            std_pin = standardize_pincode(trimmed)
            cleaned[col] = std_pin
            if trimmed and not std_pin:
                warnings.append(f"Suspicious PIN code in '{col}': '{trimmed}' (expected 6 digits)")

        elif col in ("total_amount", "tax_amount", "subtotal", "total_marks", "percentage", "unit_price", "total_price"):
            amt = parse_monetary_amount(trimmed)
            cleaned[col] = amt
            if trimmed and amt is None:
                warnings.append(f"Suspicious non-numeric value in monetary/score field '{col}': '{trimmed}'")

        else:
            cleaned[col] = trimmed

    # Auto-assign category if missing for receipts (Slide 6 #3)
    if category in ("receipts", "receipt_invoice"):
        if not cleaned.get("category"):
            cleaned["category"] = auto_categorize_receipt(
                shop_name=str(cleaned.get("shop_name") or ""),
                raw_text=str(cleaned.get("shop_name", ""))
            )

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
