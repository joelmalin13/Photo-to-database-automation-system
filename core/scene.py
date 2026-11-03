"""Scene and environment understanding module for PixelMind.

Determines the scene setting (e.g., street, park, living room, office)
and environment classification (indoor vs. outdoor) using zero-shot CLIP inference
combined with detected object composition priors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

from config.settings import load_scenes_config, logger
from core.embedder import ClipEmbedder

# Object labels with strong outdoor / indoor priors
OUTDOOR_LABELS = {
    "car", "truck", "bus", "traffic light", "fire hydrant", "stop sign", "bicycle",
    "motorcycle", "airplane", "boat", "train", "bench", "parking meter", "tree", "bird"
}
INDOOR_LABELS = {
    "couch", "bed", "dining table", "tv", "microwave", "oven", "toaster", "sink",
    "refrigerator", "toilet", "laptop", "mouse", "keyboard", "clock"
}


def classify_scene(
    image_path: Path,
    clip_embedder: Optional[ClipEmbedder] = None,
    detections: Optional[List[Any]] = None,
) -> Tuple[str, str]:
    """Classify the scene type and environment (indoor vs outdoor) for an image."""
    scenes_config = load_scenes_config()
    candidate_scenes: List[Dict[str, str]] = scenes_config.get("scenes", [])

    scene_label = "general"
    environment = "outdoor"

    # 1. Evaluate detected objects for strong environmental bias
    outdoor_count = 0
    indoor_count = 0
    if detections:
        for d in detections:
            lbl = getattr(d, "label", None) or (d.get("label") if isinstance(d, dict) else "")
            cnt = getattr(d, "count", 1) or (d.get("count", 1) if isinstance(d, dict) else 1)
            clean_lbl = lbl.lower()
            if clean_lbl in OUTDOOR_LABELS:
                outdoor_count += cnt
            elif clean_lbl in INDOOR_LABELS:
                indoor_count += cnt

    # 2. Zero-shot CLIP scene classification
    embedder = clip_embedder or ClipEmbedder.get_instance()
    if candidate_scenes and image_path.exists():
        labels = [s["label"] for s in candidate_scenes]
        best_label, score = embedder.zero_shot_classify(image_path, labels)
        scene_label = best_label

        # Lookup scene environment
        matched = next((s for s in candidate_scenes if s["label"] == best_label), None)
        if matched:
            environment = matched.get("environment", "outdoor")

    # Reconcile with object heuristics if strong consensus exists
    if outdoor_count >= 2 and indoor_count == 0:
        environment = "outdoor"
    elif indoor_count >= 2 and outdoor_count == 0:
        environment = "indoor"

    logger.info("Classified image %s -> Scene: %s, Environment: %s", image_path.name, scene_label, environment)
    return scene_label, environment
