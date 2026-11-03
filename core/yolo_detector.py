"""YOLOv8 object detector implementation using Ultralytics.

Runs CPU-friendly YOLOv8n inference, extracts bounding coordinates and confidence scores,
groups detections by label, and renders an annotated visualization with color-coded bounding boxes.
Renders visualizations with pure Pillow ImageDraw (zero OpenCV dependency).
"""

from __future__ import annotations

from collections import defaultdict
import io
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
import numpy as np
from PIL import Image as PILImage, ImageDraw

from config.settings import ANNOTATED_DIR, YOLO_MODEL_NAME, logger
from core.categorizer import get_label_category
from core.decorators import timed
from core.detector_base import BaseDetector, DetectionItem, DetectionResult
from core.exceptions import DetectionError

# Category palette for bounding boxes (RGB format for Pillow)
CATEGORY_COLORS: Dict[str, tuple[int, int, int]] = {
    "Vehicles": (220, 38, 38),         # Crimson red
    "Human activities": (37, 99, 235),  # Blue
    "Animals": (16, 185, 129),         # Green
    "Nature": (34, 197, 94),           # Forest green
    "Technology": (99, 102, 241),      # Indigo
    "Electronics": (147, 51, 234),     # Purple
    "Food": (245, 158, 11),            # Amber
    "Architecture": (13, 148, 136),    # Teal
    "Sports": (236, 72, 153),          # Pink
}
DEFAULT_BOX_COLOR = (120, 120, 120)


class YoloDetector(BaseDetector):
    """YOLOv8 object detection engine."""

    _model: Any = None

    @classmethod
    def _get_model(cls) -> Any:
        """Lazy singleton loader for the YOLOv8 model."""
        if cls._model is None:
            try:
                from ultralytics import YOLO

                logger.info("Loading YOLO model: %s (auto-download on first run)...", YOLO_MODEL_NAME)
                cls._model = YOLO(YOLO_MODEL_NAME)
                logger.info("YOLO model loaded successfully.")
            except ImportError as exc:
                raise DetectionError(
                    "Ultralytics is not installed. Please install requirements-local.txt or use AI_MODE=cloud."
                ) from exc
            except Exception as exc:
                raise DetectionError(f"Failed to load YOLO weights ({YOLO_MODEL_NAME}): {exc}") from exc
        return cls._model

    @timed
    def detect(
        self,
        image_input: Any,
        confidence_threshold: float = 0.25,
        save_annotated: bool = True,
        output_dir: Optional[Path] = None,
    ) -> DetectionResult:
        """Execute YOLOv8n object detection and produce annotated visualization."""
        if isinstance(image_input, (str, Path)):
            pil_img = PILImage.open(str(image_input)).convert("RGB")
            fname = Path(image_input).name
        elif isinstance(image_input, bytes):
            pil_img = PILImage.open(io.BytesIO(image_input)).convert("RGB")
            fname = "uploaded.jpg"
        elif isinstance(image_input, PILImage.Image):
            pil_img = image_input.convert("RGB")
            fname = "image.jpg"
        else:
            raise DetectionError("Unsupported image input type for YoloDetector.")

        model = self._get_model()

        try:
            # Ultralytics accepts PIL.Image directly
            results = model.predict(
                source=pil_img,
                conf=confidence_threshold,
                verbose=False,
            )
        except Exception as exc:
            raise DetectionError(f"YOLO inference failed: {exc}") from exc

        if not results:
            return DetectionResult(items=[], total_count=0, raw_boxes=[])

        first_res = results[0]
        boxes = first_res.boxes
        names = first_res.names or {}

        # Copy original PIL image for bounding box rendering
        annotated_img = pil_img.copy()
        draw = ImageDraw.Draw(annotated_img)

        grouped_detections: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "confidences": [], "bboxes": [], "category": "Uncategorized"}
        )
        raw_boxes: List[Dict[str, Any]] = []

        if boxes is not None and len(boxes) > 0:
            xyxy_arr = boxes.xyxy.cpu().numpy()
            conf_arr = boxes.conf.cpu().numpy()
            cls_arr = boxes.cls.cpu().numpy().astype(int)

            for i in range(len(xyxy_arr)):
                x1, y1, x2, y2 = xyxy_arr[i]
                conf = float(conf_arr[i])
                cls_id = int(cls_arr[i])
                label_name = names.get(cls_id, f"class_{cls_id}")
                cat = get_label_category(label_name)

                box_dict = {
                    "x1": int(round(x1)),
                    "y1": int(round(y1)),
                    "x2": int(round(x2)),
                    "y2": int(round(y2)),
                    "confidence": round(conf, 3),
                    "label": label_name,
                    "category": cat,
                }
                raw_boxes.append(box_dict)

                grouped = grouped_detections[label_name]
                grouped["count"] += 1
                grouped["confidences"].append(conf)
                grouped["bboxes"].append(box_dict)
                grouped["category"] = cat

                # Draw bounding box
                box_color = CATEGORY_COLORS.get(cat, DEFAULT_BOX_COLOR)
                draw.rectangle([box_dict["x1"], box_dict["y1"], box_dict["x2"], box_dict["y2"]], outline=box_color, width=3)

                # Draw label badge
                caption = f"{label_name} {int(conf * 100)}%"
                badge_bbox = draw.textbbox((box_dict["x1"], max(0, box_dict["y1"] - 18)), caption)
                draw.rectangle([badge_bbox[0] - 2, badge_bbox[1] - 2, badge_bbox[2] + 4, badge_bbox[3] + 2], fill=box_color)
                draw.text((box_dict["x1"], max(0, box_dict["y1"] - 18)), caption, fill=(255, 255, 255))

        # Save annotated image
        buf = io.BytesIO()
        annotated_img.save(buf, format="JPEG", quality=85)
        annotated_bytes = buf.getvalue()

        annotated_path_str = None
        if save_annotated:
            dest_dir = output_dir or ANNOTATED_DIR
            dest_dir.mkdir(parents=True, exist_ok=True)
            annotated_filename = f"annotated_{uuid.uuid4().hex[:10]}_{fname}"
            target_path = dest_dir / annotated_filename
            target_path.write_bytes(annotated_bytes)
            annotated_path_str = str(target_path)

        # Format detection items
        items: List[DetectionItem] = []
        for label, data in grouped_detections.items():
            avg_conf = (
                round(sum(data["confidences"]) / len(data["confidences"]), 3)
                if data["confidences"]
                else 0.0
            )
            items.append(
                DetectionItem(
                    label=label,
                    category=data["category"],
                    count=data["count"],
                    avg_confidence=avg_conf,
                    bboxes=data["bboxes"],
                )
            )

        items.sort(key=lambda x: x.count, reverse=True)
        total_count = sum(item.count for item in items)

        res = DetectionResult(
            items=items,
            total_count=total_count,
            annotated_path=annotated_path_str,
            raw_boxes=raw_boxes,
        )
        res.annotated_bytes = annotated_bytes
        return res
