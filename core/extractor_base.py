"""Abstract Base Class and factory function for SnapBase extraction engines.

Defines the polymorphic contract shared by EasyOCR (default), Tesseract, and Gemini.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

from config.settings import DEFAULT_ENGINE, GEMINI_API_KEY, logger
from core.validators import ExtractionResult


class BaseExtractor(ABC):
    """Abstract base class establishing the contract for all document extractors."""

    @abstractmethod
    def extract(
        self, image_path: Path, doc_type: str, schema: Dict[str, Any]
    ) -> ExtractionResult:
        """Extract structured fields and line items from a preprocessed document image."""
        raise NotImplementedError


def detect_document_type(text_sample: str) -> str:
    """Classify document category automatically based on heuristic keyword matching."""
    text_lower = text_sample.lower()

    # Business Card indicators
    card_signals = ["tel", "phone", "email", "www", "website", "designation", "manager", "director", "consultant", "inc", "ltd"]
    if sum(1 for s in card_signals if s in text_lower) >= 3 and ("@" in text_sample or ".com" in text_lower):
        return "business_cards"

    # Student Marksheet / ID indicators
    student_signals = [
        "student", "usn", "marks", "grade", "percentage", "semester", "subject",
        "university", "college", "roll no", "result", "distinction"
    ]
    if sum(1 for s in student_signals if s in text_lower) >= 2:
        return "students"

    # Receipts / Bills indicators
    receipt_signals = [
        "invoice", "receipt", "total", "tax", "vat", "gst", "subtotal", "payment",
        "amount due", "balance", "cashier", "bill", "shop", "qty", "item"
    ]
    if sum(1 for s in receipt_signals if s in text_lower) >= 2:
        return "receipts"

    # Default fallback
    return "receipts"


def get_extractor(engine_name: str | None = None) -> BaseExtractor:
    """Factory function instantiating the requested or default extraction engine.

    Specification: EasyOCR is the default engine. Tesseract and Gemini are optional.
    """
    chosen = (engine_name or DEFAULT_ENGINE).lower()

    if chosen == "tesseract":
        from core.tesseract_extractor import TesseractExtractor
        return TesseractExtractor()

    elif chosen == "gemini":
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not configured. Falling back to default EasyOCR engine.")
            from core.ocr_extractor import OCRExtractor
            return OCRExtractor()
        from core.gemini_extractor import GeminiExtractor
        return GeminiExtractor()

    # Default engine: EasyOCR
    from core.ocr_extractor import OCRExtractor
    return OCRExtractor()
