"""Statistical anomaly detection module for PixelMind.

Identifies images whose object composition or counts deviate significantly
from normal database distributions. Flagged images are labelled 'Needs review'
for manual human inspection. Never claims danger or safety hazards.
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple
import numpy as np


def check_image_anomaly(
    detections: List[Any],
    historical_counts: Optional[List[int]] = None,
) -> Optional[Tuple[str, float]]:
    """Determine if an image's object count or category combination is a statistical outlier."""
    if not detections:
        return None

    total_objects = sum(
        (getattr(d, "count", None) or (d.get("count", 1) if isinstance(d, dict) else 1))
        for d in detections
    )

    categories = {
        (getattr(d, "category", None) or (d.get("category", "") if isinstance(d, dict) else ""))
        for d in detections
    }

    labels = {
        (getattr(d, "label", None) or (d.get("label", "") if isinstance(d, dict) else "")).lower()
        for d in detections
    }

    # 1. Extreme object density outlier check
    if total_objects >= 12:
        z_score = round(float((total_objects - 5) / 3.0), 2)
        return (
            f"Unusual object density ({total_objects} detected objects; potential clustering). Needs review.",
            z_score,
        )

    # 2. Statistical outlier compared to historical database counts
    if historical_counts and len(historical_counts) >= 5:
        arr = np.array(historical_counts, dtype=np.float32)
        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr))
        if std_val > 0.5:
            z_score = round(float(abs(total_objects - mean_val) / std_val), 2)
            if z_score >= 2.5:
                return (
                    f"Object count ({total_objects}) is a statistical outlier (z-score: {z_score}). Needs review.",
                    z_score,
                )

    # 3. Categorical incongruity checks (e.g. Food + Heavy Transport or Architecture + Wild Animals)
    has_food = "Food" in categories
    has_vehicles = "Vehicles" in categories
    has_animals = "Animals" in categories
    has_electronics = "Electronics" in categories

    if has_food and has_vehicles and len(labels.intersection({"pizza", "cake", "sandwich"})) > 0:
        return (
            "Uncommon scene pairing (food items co-occurring with vehicles). Needs review.",
            1.85,
        )

    if has_animals and has_electronics and len(labels.intersection({"cow", "elephant", "bear", "zebra"})) > 0:
        return (
            "Uncommon scene pairing (large wildlife co-occurring with indoor electronics). Needs review.",
            2.10,
        )

    return None
