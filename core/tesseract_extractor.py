"""Tesseract OCR extractor implementation with per-word confidence.

Optional OCR engine selectable in Settings as specified in the project requirements.
Falls back safely to EasyOCR if Tesseract binary is not installed on the host.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

from config.settings import TESSERACT_CMD, logger
from core.decorators import retry, timed
from core.exceptions import ExtractionError
from core.extractor_base import BaseExtractor, detect_document_type
from core.validators import ExtractionResult


class TesseractExtractor(BaseExtractor):
    """Optional OCR extraction engine using Tesseract and regex pattern matching."""

    def __init__(self) -> None:
        self.engine_name = "tesseract"
        self._configure_cmd()

    def _configure_cmd(self) -> None:
        """Set tesseract_cmd if defined in environment or known default locations."""
        try:
            import pytesseract

            if TESSERACT_CMD and Path(TESSERACT_CMD).exists():
                pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
            else:
                # Common Windows install paths
                common_paths = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                ]
                for p in common_paths:
                    if Path(p).exists():
                        pytesseract.pytesseract.tesseract_cmd = p
                        break
        except Exception:
            pass

    @timed
    @retry(max_attempts=2, delay_seconds=1.0, exceptions=(Exception,))
    def extract(
        self, image_path: Path, doc_type: str, schema: Dict[str, Any]
    ) -> ExtractionResult:
        """Perform Tesseract OCR and extract structured fields."""
        if not image_path.exists():
            raise ExtractionError(f"Image not found at {image_path}")

        try:
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:
            logger.warning("pytesseract not installed. Delegating to EasyOCR.")
            from core.ocr_extractor import OCRExtractor

            return OCRExtractor().extract(image_path, doc_type, schema)

        try:
            img = Image.open(image_path)
            # Word-level data with bounding boxes and confidence
            data = pytesseract.image_to_data(img, output_type=Output.DICT)
            raw_text = pytesseract.image_to_string(img)
        except Exception as exc:
            logger.warning(
                "Tesseract execution failed (%s). Delegating to EasyOCR.", exc
            )
            from core.ocr_extractor import OCRExtractor

            return OCRExtractor().extract(image_path, doc_type, schema)

        lines: List[str] = [line.strip() for line in raw_text.splitlines() if line.strip()]
        word_confidences: List[Dict[str, Any]] = []
        valid_confs: List[float] = []

        n_boxes = len(data.get("text", []))
        for i in range(n_boxes):
            word = data["text"][i].strip()
            conf_str = data["conf"][i]
            try:
                conf = float(conf_str) / 100.0
            except (ValueError, TypeError):
                conf = -1.0

            if word and conf >= 0.0:
                valid_confs.append(conf)
                x, y, w, h = (
                    data["left"][i],
                    data["top"][i],
                    data["width"][i],
                    data["height"][i],
                )
                word_confidences.append(
                    {
                        "word": word,
                        "confidence": round(conf, 4),
                        "box": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
                    }
                )

        avg_ocr_conf = sum(valid_confs) / len(valid_confs) if valid_confs else 0.5

        target_type = (
            detect_document_type(raw_text) if doc_type in ("auto", "other") else doc_type
        )
        if doc_type in ("auto", "other"):
            from config.settings import load_schemas

            all_schemas = load_schemas()
            schema = all_schemas.get(target_type, schema)

        # Reuse rule-based matching
        from core.ocr_extractor import OCRExtractor

        helper = OCRExtractor()
        extracted_fields, field_confidences = helper._match_fields(
            lines, raw_text, schema.get("fields", []), avg_ocr_conf
        )

        items = []
        if target_type in ("receipts", "receipt_invoice"):
            items = helper._parse_receipt_items(lines)
        elif target_type in ("students", "student_marksheet", "student_id_form"):
            items = helper._parse_student_marks(lines)

        return ExtractionResult(
            doc_type=target_type,
            fields=extracted_fields,
            confidences=field_confidences,
            line_items=items,
            raw_text=raw_text,
            engine_used="Tesseract",
            word_confidences=word_confidences,
        )
