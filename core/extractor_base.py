"""Abstract Base Class and factory function for SnapBase extraction engines.

Defines the polymorphic contract shared by Gemini vision and offline OCR engines.
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
        """Extract structured fields and line items from a preprocessed document image.

        Args:
            image_path: Filesystem path to the preprocessed image.
            doc_type: Document classification category.
            schema: Field definitions and extraction rules from schemas.json.

        Returns:
            ExtractionResult: Structured container holding fields, scores, and text.
        """
        raise NotImplementedError


def detect_document_type(text_sample: str) -> str:
    """Classify document category automatically based on heuristic keyword matching.

    Args:
        text_sample: Extracted or OCR-recognized textual content.

    Returns:
        str: Detected document type identifier.
    """
    text_lower = text_sample.lower()

    # Student / ID indicators
    id_signals = [
        "student",
        "identity",
        "id card",
        "roll no",
        "university",
        "college",
        "blood group",
        "dob",
        "date of birth",
    ]
    if sum(1 for s in id_signals if s in text_lower) >= 2:
        return "student_id_form"

    # Receipt / Invoice indicators
    receipt_signals = [
        "invoice",
        "receipt",
        "total",
        "tax",
        "vat",
        "subtotal",
        "payment",
        "amount due",
        "balance",
        "cashier",
        "bill",
    ]
    if sum(1 for s in receipt_signals if s in text_lower) >= 2:
        return "receipt_invoice"

    # Table indicators
    table_signals = ["table", "qty", "item", "unit price", "description", "rate"]
    if sum(1 for s in table_signals if s in text_lower) >= 2:
        return "generic_table"

    # Default fallback
    return "receipt_invoice"


def get_extractor(engine_name: str | None = None) -> BaseExtractor:
    """Factory function instantiating the requested or default extraction engine.

    Args:
        engine_name: 'gemini' or 'ocr'. Defaults to system configuration.

    Returns:
        BaseExtractor: Concrete polymorphic extractor instance.
    """
    chosen = (engine_name or DEFAULT_ENGINE).lower()

    if chosen == "gemini":
        if not GEMINI_API_KEY:
            logger.warning(
                "GEMINI_API_KEY not configured. Falling back to offline OCR engine."
            )
            from core.ocr_extractor import OCRExtractor

            return OCRExtractor()
        from core.gemini_extractor import GeminiExtractor

        return GeminiExtractor()

    from core.ocr_extractor import OCRExtractor

    return OCRExtractor()
