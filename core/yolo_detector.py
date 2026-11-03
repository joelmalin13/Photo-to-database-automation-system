"""YOLOv8 object detector implementation using Ultralytics.

Runs CPU-friendly YOLOv8n inference, extracts bounding coordinates and confidence scores,
groups detections by label, and renders an annotated visualization with color-coded bounding boxes.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
import cv2
import numpy as np

from config.settings import ANNOTATED_DIR, YOLO_MODEL_NAME, logger
from core.categorizer import get_label_category
from core.decorators import timed
from core.detector_base import BaseDetector, DetectionItem, DetectionResult
from core.exceptions import DetectionError

# Category palette for bounding boxes (BGR format for OpenCV)
CATEGORY_COLORS: Dict[str, tuple[int, int, int]] = {
    "Vehicles": (40, 40, 198),         # Crimson red
    "Human activities": (198, 90, 40), # Coral / orange
    "Animals": (40, 180, 40),          # Green
    "Nature": (30, 150, 80),           # Forest green
    "Technology": (180, 130, 30),      # Blue/teal
    "Electronics": (200, 160, 20),     # Azure
    "Food": (30, 180, 210),            # Gold / yellow
    "Architecture": (120, 120, 120),   # Gray
    "Sports": (160, 40, 180),          # Purple
}
DEFAULT_BOX_COLOR = (70, 70, 70)


class YoloDetector(BaseDetector):
    """YOLOv8 object detection engine."""

    _model: Any = None

    @classmethod
    def _get_model(cls) -> Any:
        """Lazy singleton loader for the YOLOv8 model."""
        if cls._model is None:
            from ultralytics import YOLO

            logger.info("Loading YOLO model: %s (auto-download on first run)...", YOLO_MODEL_NAME)
            cls._model = YOLO(YOLO_MODEL_NAME)
            logger.info("YOLO model loaded successfully.")
        return cls._model

    @timed
    def detect(
        self,
        image_path: Path,
        confidence_threshold: float = 0.25,
        save_annotated: bool = True,
        output_dir: Optional[Path] = None,
    ) -> DetectionResult:
        """Execute object detection and generate annotated bounding boxes."""
        if not image_path.exists():
            raise DetectionError(f"Image not found at {image_path}")

        try:
            model = self._get_model()
            results = model.predict(
                source=str(image_path),
                conf=confidence_threshold,
                verbose=False,
            )
        except Exception as exc:
            logger.error("YOLO inference failed: %s", exc)
            raise DetectionError(f"Object detection inference failed: {exc}") from exc

        if not results:
            return DetectionResult(items=[], total_count=0, annotated_path=None, raw_boxes=[])

        first_res = results[0]
        boxes = first_res.boxes
        names = first_res.names or {}

        # Read original image for custom bounding box rendering
        orig_img = cv2.imread(str(image_path))
        if orig_img is None:
            raise DetectionError(f"OpenCV could not read image at {image_path}")

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

                # Draw bounding box on original image
                box_color = CATEGORY_COLORS.get(cat, DEFAULT_BOX_COLOR)
                cv2.rectangle(
                    orig_img,
                    (int(x1), int(y1)),
                    (int(x2), int(y2)),
                    box_color,
                    2,
                )

                # Draw label badge
                caption = f"{label_name} {int(conf * 100)}%"
                (w, h), _ = cv2.getTextSize(caption, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                badge_y1 = max(0, int(y1) - h - 6)
                badge_y2 = int(y1)
                cv2.rectangle(
                    orig_img,
                    (int(x1), badge_y1),
                    (int(x1) + w + 8, badge_y2),
                    box_color,
                    -1,
                )
                cv2.putText(
                    orig_img,
                    caption,
                    (int(x1) + 4, badge_y2 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )

        # Save annotated image
        annotated_path_str = None
        if save_annotated:
            dest_dir = output_dir or ANNOTATED_DIR
            dest_dir.mkdir(parents=True, exist_ok=True)
            annotated_filename = f"annotated_{uuid.uuid4().hex[:10]}_{image_path.name}"
            target_path = dest_dir / annotated_filename
            cv2.imwrite(str(target_path), orig_img)
            annotated_path_str = str(target_path)

        # Format detection items
        items: List[DetectionItem] = []
        total_count = 0
        for lbl, data in grouped_detections.items():
            cnt = data["count"]
            total_count += cnt
            avg_conf = sum(data["confidences"]) / len(data["confidences"]) if data["confidences"] else 0.0
            items.append(
                DetectionItem(
                    label=lbl,
                    category=data["category"],
                    count=cnt,
                    avg_confidence=round(avg_conf, 3),
                    bboxes=data["bboxes"],
                )
            )

        # Sort items by count descending
        items.sort(key=lambda it: it.count, reverse=True)

        return DetectionResult(
            items=items,
            total_count=total_count,
            annotated_path=annotated_path_str,
            raw_boxes=raw_boxes,
        )
