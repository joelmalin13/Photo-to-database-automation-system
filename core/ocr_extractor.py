"""Offline OCR extractor using EasyOCR and schema-driven regex parsing.

Provides local, API-key-free document extraction with bounding box confidence
aggregation and line-item pattern parsing.
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
    """Offline extraction engine combining EasyOCR and rule-based regex parsing."""

    def __init__(self) -> None:
        """Initialize OCR engine."""
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

        # Extract text and average OCR line confidences
        lines: List[str] = []
        confidences_list: List[float] = []
        for bbox, text, score in results:
            cleaned = text.strip()
            if cleaned:
                lines.append(cleaned)
                confidences_list.append(float(score))

        raw_text = "\n".join(lines)
        avg_ocr_conf = (
            sum(confidences_list) / len(confidences_list)
            if confidences_list
            else 0.5
        )

        # Auto-detect doc type if auto requested
        target_type = (
            detect_document_type(raw_text) if doc_type == "auto" else doc_type
        )
        if doc_type == "auto" and target_type in (
            "student_id_form",
            "generic_table",
        ):
            from config.settings import load_schemas

            all_schemas = load_schemas()
            schema = all_schemas.get(target_type, schema)

        extracted_fields, field_confidences = self._match_fields(
            lines, raw_text, schema.get("fields", []), avg_ocr_conf
        )

        line_items = (
            self._parse_line_items(lines)
            if schema.get("supports_line_items", False)
            else []
        )

        return ExtractionResult(
            doc_type=target_type,
            fields=extracted_fields,
            confidences=field_confidences,
            line_items=line_items,
            raw_text=raw_text,
            engine_used="ocr",
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
            match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
            if match:
                extracted = match.group(1).strip()
                return extracted, round(min(0.95, base_confidence + 0.15), 2)

            # Check individual lines
            for line in lines:
                line_match = re.search(pattern, line, re.IGNORECASE)
                if line_match:
                    extracted = line_match.group(1).strip()
                    return extracted, round(min(0.92, base_confidence + 0.1), 2)

        return None, 0.0

    def _parse_line_items(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Identify potential tabular line items with quantities and prices."""
        items: List[Dict[str, Any]] = []
        # Pattern for: Item Description ... Qty x Price or Amount
        pattern = re.compile(
            r"^(?P<desc>[A-Za-z0-9\s\-_]{3,30}?)\s+(?P<qty>\d+)?\s*[$€£]?\s*(?P<price>\d+[.,]\d{2})$"
        )
        for line in lines:
            m = pattern.match(line.strip())
            if m:
                desc = m.group("desc").strip()
                qty = int(m.group("qty")) if m.group("qty") else 1
                price_str = m.group("price").replace(",", ".")
                price = float(price_str)
                items.append(
                    {
                        "description": desc,
                        "quantity": qty,
                        "unit_price": price,
                        "amount": round(qty * price, 2),
                    }
                )
        return items
