"""Cloud-based visual object detector powered by Google Gemini 2.5 Flash.

Performs zero-dependency object detection, scene classification, environment determination,
and visual captioning via a single structured JSON inference request.
Draws bounding boxes using pure Pillow (PIL.ImageDraw) with zero OpenCV or PyTorch dependencies.
"""

from __future__ import annotations

import io
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image as PILImage, ImageDraw, ImageFont
import pydantic
from pydantic import BaseModel, Field

from config.settings import GEMINI_API_KEY, GEMINI_MODEL, logger
from core.categorizer import get_label_category
from core.decorators import retry, timed
from core.detector_base import BaseDetector, DetectionItem, DetectionResult
from core.exceptions import DetectionError

# Palette colors per category for visual bounding boxes
CATEGORY_COLORS: Dict[str, Tuple[int, int, int]] = {
    "Vehicles": (220, 38, 38),       # Red
    "Animals": (16, 185, 129),       # Emerald
    "Human activities": (37, 99, 235), # Blue
    "Electronics": (147, 51, 234),   # Purple
    "Food": (245, 158, 11),          # Amber
    "Architecture": (13, 148, 136),   # Teal
    "Nature": (34, 197, 94),         # Green
    "Sports": (236, 72, 153),        # Pink
    "Technology": (99, 102, 241),    # Indigo
}
DEFAULT_BOX_COLOR = (120, 120, 120)


class DetectedObjectSchema(BaseModel):
    """Schema for individual detected objects from Gemini."""

    label: str = Field(description="Recognized object label e.g. car, dog, person, laptop")
    count: int = Field(default=1, description="Count of this specific object instance")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Certainty score from 0.0 to 1.0")
    # Normalized bounding box: [ymin, xmin, ymax, xmax] from 0.0 to 1.0
    box_2d: List[float] = Field(default_factory=list, description="Normalized coordinates [ymin, xmin, ymax, xmax] (0.0 to 1.0)")


class GeminiVisionSchema(BaseModel):
    """Structured response schema returned by Gemini vision call."""

    objects: List[DetectedObjectSchema] = Field(default_factory=list)
    caption: str = Field(description="One concise factual sentence describing the image")
    scene: str = Field(default="general", description="Scene type e.g. street, park, office, living room, kitchen, forest")
    environment: str = Field(default="outdoor", description="Either 'indoor' or 'outdoor'")
    context: str = Field(default="", description="Brief visual context")
    category: str = Field(
        default="Technology",
        description="Best matching canonical category: Nature, Animals, Vehicles, Technology, Food, Architecture, Human activities, Sports, Electronics",
    )


class CloudDetector(BaseDetector):
    """Detector implementation using Google Gemini 2.5 Flash multimodal vision."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None) -> None:
        self.api_key = api_key or GEMINI_API_KEY
        self.model_name = model_name or GEMINI_MODEL
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.api_key:
                raise DetectionError(
                    "GEMINI_API_KEY is not configured. Please set GEMINI_API_KEY in your environment or Settings."
                )
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as exc:
                raise DetectionError(f"Failed to initialize Gemini Client: {exc}") from exc
        return self._client

    @retry(max_attempts=2, delay_seconds=1.0)
    def _call_gemini_vision(self, pil_image: PILImage.Image) -> GeminiVisionSchema:
        """Execute Gemini 2.5 Flash vision call with Pydantic response schema."""
        client = self._get_client()
        from google.genai import types

        # Prepare downsampled JPEG in-memory buffer
        max_dim = 1600
        w, h = pil_image.size
        if max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            pil_image = pil_image.resize((int(w * scale), int(h * scale)), PILImage.Resampling.LANCZOS)

        buf = io.BytesIO()
        pil_image.convert("RGB").save(buf, format="JPEG", quality=85)
        image_bytes = buf.getvalue()

        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

        prompt = (
            "Analyze this photograph with high precision. "
            "Identify all prominent visual objects, bounding box coordinates [ymin, xmin, ymax, xmax] between 0.0 and 1.0, "
            "count, confidence score, scene type, indoor/outdoor environment, a single concise caption, "
            "and the overall canonical category (one of: Nature, Animals, Vehicles, Technology, Food, Architecture, Human activities, Sports, Electronics)."
        )

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeminiVisionSchema,
            temperature=0.2,
        )

        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=[image_part, prompt],
                config=config,
            )

            if not response.text:
                raise DetectionError("Gemini returned empty response text.")

            return GeminiVisionSchema.model_validate_json(response.text)

        except Exception as exc:
            err_msg = str(exc)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                raise DetectionError("Gemini AI rate limit reached (429). Please retry in a few moments.") from exc
            raise DetectionError(f"Gemini Vision call failed: {exc}") from exc

    def _render_boxes_pillow(
        self,
        pil_image: PILImage.Image,
        objects: List[DetectedObjectSchema],
    ) -> Tuple[PILImage.Image, List[Dict[str, Any]]]:
        """Draw bounding boxes and label badges using pure Pillow (no OpenCV)."""
        annotated = pil_image.copy().convert("RGB")
        draw = ImageDraw.Draw(annotated)
        width, height = annotated.size

        raw_boxes: List[Dict[str, Any]] = []

        for obj in objects:
            lbl = obj.label.strip().lower()
            cat = get_label_category(lbl)
            color = CATEGORY_COLORS.get(cat, DEFAULT_BOX_COLOR)

            # Check if normalized box [ymin, xmin, ymax, xmax] is provided
            if obj.box_2d and len(obj.box_2d) >= 4:
                ymin, xmin, ymax, xmax = obj.box_2d[:4]
                x1 = int(round(xmin * width))
                y1 = int(round(ymin * height))
                x2 = int(round(xmax * width))
                y2 = int(round(ymax * height))
            else:
                # Default mock box if not localized
                x1, y1, x2, y2 = 10, 10, min(width - 10, 150), min(height - 10, 150)

            # Clamp coordinates
            x1 = max(0, min(width - 1, x1))
            y1 = max(0, min(height - 1, y1))
            x2 = max(x1 + 1, min(width, x2))
            y2 = max(y1 + 1, min(height, y2))

            box_dict = {
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "confidence": round(float(obj.confidence), 3),
                "label": lbl,
                "category": cat,
            }
            raw_boxes.append(box_dict)

            # Draw outer rectangle (thickness 3)
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

            # Draw label tag
            caption_text = f"{lbl} {int(obj.confidence * 100)}%"
            # Text background badge
            text_bbox = draw.textbbox((x1, max(0, y1 - 18)), caption_text)
            draw.rectangle([text_bbox[0] - 2, text_bbox[1] - 2, text_bbox[2] + 4, text_bbox[3] + 2], fill=color)
            draw.text((x1, max(0, y1 - 18)), caption_text, fill=(255, 255, 255))

        return annotated, raw_boxes

    @timed
    def detect(
        self,
        image_input: Any,  # Path or bytes or PIL.Image
        confidence_threshold: float = 0.25,
        save_annotated: bool = True,
        output_dir: Optional[Path] = None,
    ) -> DetectionResult:
        """Run cloud object detection via Gemini 2.5 Flash."""
        # 1. Load PIL Image
        if isinstance(image_input, (str, Path)):
            pil_image = PILImage.open(str(image_input)).convert("RGB")
            filename = Path(image_input).name
        elif isinstance(image_input, bytes):
            pil_image = PILImage.open(io.BytesIO(image_input)).convert("RGB")
            filename = "uploaded.jpg"
        elif isinstance(image_input, PILImage.Image):
            pil_image = image_input.convert("RGB")
            filename = "image.jpg"
        else:
            raise DetectionError("Unsupported image input type for CloudDetector.")

        # 2. Call Gemini
        vision_res = self._call_gemini_vision(pil_image)

        # 3. Filter objects by confidence
        filtered_objs = [
            obj for obj in vision_res.objects
            if float(obj.confidence) >= confidence_threshold
        ]

        # 4. Render bounding boxes with Pillow
        annotated_img, raw_boxes = self._render_boxes_pillow(pil_image, filtered_objs)

        # 5. Save annotated image bytes or to disk
        buf = io.BytesIO()
        annotated_img.save(buf, format="JPEG", quality=85)
        annotated_bytes = buf.getvalue()

        annotated_path_str: Optional[str] = None
        if save_annotated and output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            target = output_dir / f"annotated_{filename}"
            target.write_bytes(annotated_bytes)
            annotated_path_str = str(target)

        # 6. Group items
        grouped: Dict[str, Dict[str, Any]] = {}
        for obj, box in zip(filtered_objs, raw_boxes):
            lbl = box["label"]
            cat = box["category"]
            conf = box["confidence"]
            cnt = max(1, getattr(obj, "count", 1))
            if lbl not in grouped:
                grouped[lbl] = {
                    "label": lbl,
                    "category": cat,
                    "count": 0,
                    "confidences": [],
                    "bboxes": [],
                }
            grouped[lbl]["count"] += cnt
            grouped[lbl]["confidences"].append(conf)
            grouped[lbl]["bboxes"].append(box)

        items: List[DetectionItem] = [
            DetectionItem(
                label=d["label"],
                category=d["category"],
                count=d["count"],
                avg_confidence=round(sum(d["confidences"]) / max(1, len(d["confidences"])), 3),
                bboxes=d["bboxes"],
            )
            for d in grouped.values()
        ]

        total_count = sum(item.count for item in items)

        result = DetectionResult(
            items=items,
            total_count=total_count,
            annotated_path=annotated_path_str,
            raw_boxes=raw_boxes,
        )
        result.annotated_bytes = annotated_bytes
        result.caption = vision_res.caption
        result.scene = vision_res.scene
        result.environment = vision_res.environment
        result.context = vision_res.context
        result.category = vision_res.category
        return result
