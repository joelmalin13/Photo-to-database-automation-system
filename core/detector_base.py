"""Abstract Base Class and factory for visual object detectors.

Supports dual operating modes:
- Cloud Mode: CloudDetector (Google Gemini 2.5 Flash structured vision)
- Local Mode: LocalDetector (Ultralytics YOLOv8n)
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
    annotated_bytes: Optional[bytes] = None
    raw_boxes: List[Dict[str, Any]] = field(default_factory=list)
    caption: Optional[str] = None
    scene: Optional[str] = None
    environment: Optional[str] = None
    category: Optional[str] = None


class BaseDetector(ABC):
    """Abstract interface defining object detection contracts."""

    @abstractmethod
    def detect(
        self,
        image_input: Any,
        confidence_threshold: float = 0.25,
        save_annotated: bool = True,
        output_dir: Optional[Path] = None,
    ) -> DetectionResult:
        """Run object detection on the target image and return structured results."""
        raise NotImplementedError


class LocalDetector(BaseDetector):
    """Local YOLOv8n detector with lazy imports of ultralytics."""

    def __init__(self) -> None:
        self._inner: Optional[BaseDetector] = None

    def _get_inner(self) -> BaseDetector:
        if self._inner is None:
            try:
                from core.yolo_detector import YoloDetector
                self._inner = YoloDetector()
            except ImportError as exc:
                raise ImportError(
                    f"Local object detection requires packages in requirements-local.txt ({exc}). "
                    "Alternatively, set AI_MODE=cloud in your environment."
                ) from exc
        return self._inner

    def detect(
        self,
        image_input: Any,
        confidence_threshold: float = 0.25,
        save_annotated: bool = True,
        output_dir: Optional[Path] = None,
    ) -> DetectionResult:
        return self._get_inner().detect(
            image_input=image_input,
            confidence_threshold=confidence_threshold,
            save_annotated=save_annotated,
            output_dir=output_dir,
        )


def get_detector(mode: Optional[str] = None) -> BaseDetector:
    """Factory function returning the configured object detector implementation."""
    from config.settings import AI_MODE
    import os

    target_mode = (mode or os.getenv("AI_MODE") or AI_MODE).strip().lower()
    if target_mode == "cloud" or bool(os.getenv("VERCEL")):
        from core.cloud_detector import CloudDetector
        return CloudDetector()

    return LocalDetector()
