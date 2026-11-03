"""Service layer for interactive image enhancement playground and OCR evaluation.

Supports real-time side-by-side processing, manual parameter tuning,
and word-level OCR confidence extraction.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any, Dict, List, Optional
import cv2
import numpy as np

from config.settings import UPLOAD_DIR, load_schemas
from core.extractor_base import detect_document_type, get_extractor
from core.preprocess import apply_custom_enhancements


class ImageProcessingService:
    """Manages custom computer vision filter pipelines and interactive OCR retries."""

    @staticmethod
    def process_and_preview(
        image_bytes: bytes,
        rotate_deg: float = 0.0,
        grayscale: bool = True,
        denoise: bool = True,
        gaussian_blur: bool = False,
        sharpen: bool = False,
        threshold_method: str = "none",
        clahe: bool = True,
        perspective: bool = False,
        run_ocr: bool = False,
        engine_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Apply requested enhancement transformations and optionally run OCR."""
        processed_arr, meta = apply_custom_enhancements(
            image_bytes=image_bytes,
            rotate_deg=rotate_deg,
            grayscale=grayscale,
            denoise=denoise,
            gaussian_blur=gaussian_blur,
            sharpen=sharpen,
            threshold_method=threshold_method,
            clahe=clahe,
            perspective=perspective,
        )

        # Encode processed image to base64 for live side-by-side UI rendering
        _, buffer = cv2.imencode(".png", processed_arr)
        proc_b64 = base64.b64encode(buffer).decode("utf-8")

        # Encode original image
        orig_b64 = base64.b64encode(image_bytes).decode("utf-8")

        ocr_data = None
        if run_ocr:
            # Save temporarily to disk for extractor
            temp_path = UPLOAD_DIR / "temp_processing_preview.png"
            cv2.imwrite(str(temp_path), processed_arr)

            extractor = get_extractor(engine_name)
            schemas = load_schemas()
            # Initial auto-detection
            res = extractor.extract(temp_path, "auto", schemas.get("receipts", {}))

            ocr_data = {
                "detected_category": res.doc_type,
                "raw_text": res.raw_text,
                "engine_used": res.engine_used,
                "word_confidences": res.word_confidences,
                "extracted_fields": res.fields,
                "field_confidences": res.confidences,
            }

        return {
            "original_image_base64": f"data:image/jpeg;base64,{orig_b64}",
            "processed_image_base64": f"data:image/png;base64,{proc_b64}",
            "metadata": meta,
            "ocr_result": ocr_data,
        }
