"""Abstract Base Class and data models for visual object detectors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DetectionItem:
    """Aggregated detection metrics for a specific object class."""

    label: str
    category: str
    count: int
    avg_confidence: float
    bboxes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DetectionResult:
    """Complete outcome of visual object detection for an image."""

    items: List[DetectionItem]
    total_count: int
    annotated_path: Optional[str] = None
    raw_boxes: List[Dict[str, Any]] = field(default_factory=list)


class BaseDetector(ABC):
    """Abstract interface defining object detection contracts."""

    @abstractmethod
    def detect(
        self,
        image_path: Path,
        confidence_threshold: float = 0.25,
        save_annotated: bool = True,
        output_dir: Optional[Path] = None,
    ) -> DetectionResult:
        """Run object detection on the target image and return structured results."""
        raise NotImplementedError


def get_detector(name: str = "yolo") -> BaseDetector:
    """Factory function returning the configured object detector implementation."""
    name_clean = name.strip().lower()
    if name_clean in ("yolo", "yolov8", "default"):
        from core.yolo_detector import YoloDetector

        return YoloDetector()
    raise ValueError(f"Unsupported detector implementation: {name}")
