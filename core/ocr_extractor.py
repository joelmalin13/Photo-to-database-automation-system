"""Offline OCR extractor using EasyOCR and schema-driven regex parsing.

Provides local, API-key-free document extraction with bounding box confidence
aggregation, word-level scores, and line-item pattern parsing.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from config.settings import logger
from core.decorators import retry, timed
from core.exceptions import ExtractionError
from core.extractor_base import BaseExtractor, detect_document_type
from core.validators import ExtractionResult

_EASYOCR_READER = None


def get_ocr_reader() -> Any:
    """Lazily load and cache EasyOCR reader instance for English language."""
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        try:
            import easyocr

            logger.info("Initializing EasyOCR reader (CPU mode)...")
            _EASYOCR_READER = easyocr.Reader(["en"], gpu=False)
            logger.info("EasyOCR reader initialized successfully.")
        except Exception as exc:
            logger.error("Failed to load easyocr: %s", exc)
            raise ExtractionError(
                f"EasyOCR initialization failed: {exc}"
            ) from exc
    return _EASYOCR_READER


class OCRExtractor(BaseExtractor):
    """Default offline extraction engine combining EasyOCR and rule-based regex parsing."""

    def __init__(self) -> None:
        self.engine_name = "easyocr"

    @timed
    @retry(max_attempts=2, delay_seconds=1.0, exceptions=(Exception,))
    def extract(
        self, image_path: Path, doc_type: str, schema: Dict[str, Any]
    ) -> ExtractionResult:
        """Perform OCR recognition on image and extract structured fields."""
        if not image_path.exists():
            raise ExtractionError(f"Image not found at {image_path}")

        reader = get_ocr_reader()
        try:
            results = reader.readtext(str(image_path))
        except Exception as exc:
            raise ExtractionError(f"OCR execution failed: {exc}") from exc

        lines: List[str] = []
        confidences_list: List[float] = []
        word_confidences: List[Dict[str, Any]] = []

        for bbox, text, score in results:
            cleaned = text.strip()
            if cleaned:
                lines.append(cleaned)
                score_val = float(score)
                confidences_list.append(score_val)
                # Word-level breakdown
                word_confidences.append(
                    {
                        "word": cleaned,
                        "confidence": round(score_val, 4),
                        "box": [[int(p[0]), int(p[1])] for p in bbox]
                        if isinstance(bbox, (list, tuple))
                        else [],
                    }
                )

        raw_text = "\n".join(lines)
        avg_ocr_conf = (
            sum(confidences_list) / len(confidences_list)
            if confidences_list
            else 0.5
        )

        target_type = (
            detect_document_type(raw_text) if doc_type in ("auto", "other") else doc_type
        )
        if doc_type in ("auto", "other"):
            from config.settings import load_schemas

            all_schemas = load_schemas()
            schema = all_schemas.get(target_type, schema)

        extracted_fields, field_confidences = self._match_fields(
            lines, raw_text, schema.get("fields", []), avg_ocr_conf
        )

        # Parse sub-items (receipt items or student marks)
        items = []
        if target_type in ("receipts", "receipt_invoice"):
            items = self._parse_receipt_items(lines)
        elif target_type in ("students", "student_marksheet", "student_id_form"):
            items = self._parse_student_marks(lines)

        return ExtractionResult(
            doc_type=target_type,
            fields=extracted_fields,
            confidences=field_confidences,
            line_items=items,
            raw_text=raw_text,
            engine_used="EasyOCR",
            word_confidences=word_confidences,
        )

    def _match_fields(
        self,
        lines: List[str],
        raw_text: str,
        field_defs: List[Dict[str, Any]],
        base_confidence: float,
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Match schema regex patterns against OCR text and determine field confidence."""
        fields: Dict[str, Any] = {}
        confidences: Dict[str, float] = {}

        for f in field_defs:
            key = f["key"]
            patterns = f.get("regex_patterns", [])
            val, conf = self._find_first_pattern_match(
                patterns, raw_text, lines, base_confidence
            )
            if val and key == "shop_name" and "\n" in val:
                val = val.split("\n")[0].strip()
            fields[key] = val
            confidences[key] = conf

        return fields, confidences

    def _find_first_pattern_match(
        self,
        patterns: List[str],
        raw_text: str,
        lines: List[str],
        base_confidence: float,
    ) -> Tuple[Optional[str], float]:
        """Search regex patterns against full raw text and individual lines."""
        for pattern in patterns:
            # Check multiline against full text first
            try:
                match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    extracted = match.group(1).strip()
                    return extracted, round(min(0.96, base_confidence + 0.15), 2)
            except Exception:
                pass

            # Check individual lines
            for line in lines:
                try:
                    line_match = re.search(pattern, line, re.IGNORECASE)
                    if line_match:
                        extracted = line_match.group(1).strip()
                        return extracted, round(min(0.93, base_confidence + 0.1), 2)
                except Exception:
                    pass

        return None, 0.0

    def _parse_receipt_items(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Identify potential tabular receipt line items with quantities and prices."""
        items: List[Dict[str, Any]] = []
        pattern = re.compile(
            r"^(?P<desc>[A-Za-z0-9\s\-_]{3,35}?)\s+(?P<qty>\d+)?\s*[$€£₹]?\s*(?P<price>\d+[.,]\d{2})$"
        )
        for line in lines:
            m = pattern.match(line.strip())
            if m:
                desc = m.group("desc").strip()
                # Skip header-like keywords
                if desc.lower() in ("total", "subtotal", "tax", "gst", "amount", "change"):
                    continue
                qty = float(m.group("qty")) if m.group("qty") else 1.0
                price_str = m.group("price").replace(",", ".")
                price = float(price_str)
                items.append(
                    {
                        "item_name": desc,
                        "description": desc,
                        "quantity": qty,
                        "unit_price": price,
                        "total_price": round(qty * price, 2),
                    }
                )
        return items

    def _parse_student_marks(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Identify academic subjects and marks scored."""
        marks: List[Dict[str, Any]] = []
        # Pattern for: Subject Name/Code ... Marks / Max
        pattern = re.compile(
            r"^(?P<code>[A-Z0-9]{3,8}\b)?\s*(?P<name>[A-Za-z\s]{3,30}?)\s+(?P<marks>\d{1,3}(?:\.\d+)?)\s*(?:/\s*(?P<max>\d{2,3}))?$"
        )
        for line in lines:
            m = pattern.match(line.strip())
            if m:
                name = m.group("name").strip()
                if name.lower() in ("total", "percentage", "grand total", "result", "cgpa"):
                    continue
                code = m.group("code") or ""
                obt = float(m.group("marks"))
                max_m = float(m.group("max")) if m.group("max") else 100.0
                marks.append(
                    {
                        "subject_name": name,
                        "subject_code": code,
                        "marks_obtained": obt,
                        "max_marks": max_m,
                    }
                )
        return marks
