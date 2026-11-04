"""Gemini Vision extractor utilizing the official google-genai SDK.

Extracts structured schema fields, confidence scores, and line items
with strict JSON response formatting and automated retries.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Dict

from google import genai
from google.genai import types
from PIL import Image

from config.settings import GEMINI_API_KEY, GEMINI_MODEL, logger
from core.decorators import retry, timed
from core.exceptions import ExtractionError
from core.extractor_base import BaseExtractor
from core.validators import ExtractionResult


class GeminiExtractor(BaseExtractor):
    """Extraction engine leveraging Google Gemini Vision multimodal models."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """Initialize Gemini client with API credentials and model version."""
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ExtractionError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in .env."
            )
        self.model_name = model or GEMINI_MODEL
        self.client = genai.Client(api_key=self.api_key)

    def _build_prompt(self, doc_type: str, schema: Dict[str, Any]) -> str:
        """Construct structured JSON generation prompt based on schema definition."""
        fields_desc = []
        for f in schema.get("fields", []):
            req_str = "REQUIRED" if f.get("required") else "OPTIONAL"
            fields_desc.append(
                f"- '{f['key']}' ({f.get('type')}, {req_str}): {f.get('description', '')}"
            )
        fields_bullet_list = "\n".join(fields_desc)
        supports_items = schema.get("supports_line_items", False)

        return f"""You are an expert document OCR and structured data extraction AI.
Analyze the provided document photograph and extract values matching this schema.
Target Document Type: {doc_type}

Fields to extract:
{fields_bullet_list}

Support Line Items: {supports_items}

Respond ONLY with valid, strict JSON matching this exact structure:
{{
  "detected_type": "{doc_type}",
  "fields": {{
    "<field_key>": "<extracted_value or null>"
  }},
  "confidences": {{
    "<field_key>": <confidence float between 0.0 and 1.0>
  }},
  "line_items": [
    {{"description": "Item A", "quantity": 1, "unit_price": 10.0, "amount": 10.0}}
  ],
  "raw_text": "<full transcript of all visible text>"
}}
No explanations, no markdown ticks, raw JSON only."""

    @timed
    @retry(max_attempts=3, delay_seconds=1.5, exceptions=(Exception,))
    def extract(
        self, image_path: Path, doc_type: str, schema: Dict[str, Any]
    ) -> ExtractionResult:
        """Extract structured fields using Gemini multimodal vision API."""
        if not image_path.exists():
            raise ExtractionError(f"Image not found at {image_path}")

        prompt = self._build_prompt(doc_type, schema)
        logger.info("Sending %s to Gemini (%s)", image_path.name, self.model_name)

        try:
            with Image.open(image_path) as pil_img:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[pil_img, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
            return self._parse_response(response.text, doc_type)
        except Exception as exc:
            logger.error("Gemini API call failed for %s: %s", image_path.name, exc)
            raise ExtractionError(f"Gemini API extraction failed: {exc}") from exc

    def _parse_response(self, text: str, default_type: str) -> ExtractionResult:
        """Parse strict JSON response and format into ExtractionResult."""
        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as err:
            logger.error("Failed to parse Gemini response as JSON: %s", text)
            raise ExtractionError(f"Malformed JSON from Gemini: {err}") from err

        fields = payload.get("fields", {})
        confidences = payload.get("confidences", {})
        line_items = payload.get("line_items", [])
        raw_text = payload.get("raw_text", "")
        detected_type = payload.get("detected_type", default_type)

        return ExtractionResult(
            doc_type=detected_type,
            fields=fields,
            confidences={k: float(v) for k, v in confidences.items()},
            line_items=line_items,
            raw_text=raw_text,
            engine_used="gemini",
        )
