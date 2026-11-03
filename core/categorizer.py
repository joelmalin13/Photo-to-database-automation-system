"""Automatic categorization module for PixelMind.

Maps detected YOLO object labels to canonical categories based on config/categories.json.
Determines image-level categorization via object frequency weighting, with CLIP
zero-shot classification as an automated tie-breaker when detections are ambiguous or absent.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional
from config.settings import load_categories_config, load_scenes_config, logger

_CATEGORIES_MAP: Optional[Dict[str, str]] = None


def get_categories_map() -> Dict[str, str]:
    """Retrieve or cached category mappings loaded from config/categories.json."""
    global _CATEGORIES_MAP
    if _CATEGORIES_MAP is None:
        _CATEGORIES_MAP = load_categories_config()
    return _CATEGORIES_MAP


def get_label_category(label: str) -> str:
    """Map a detected object label (e.g. 'car', 'dog') to its canonical category."""
    cat_map = get_categories_map()
    clean_lbl = label.strip().lower()
    return cat_map.get(clean_lbl, "Technology")


def determine_image_category(
    detections: List[Any],
    image_path: Optional[Path] = None,
    clip_embedder: Optional[Any] = None,
) -> str:
    """Assign an image-level category from its detected objects or zero-shot CLIP classification."""
    # 1. Frequency of detected object categories
    if detections:
        category_weights: Counter[str] = Counter()
        for item in detections:
            # Handle both DetectionItem and raw dicts
            cat = getattr(item, "category", None) or (item.get("category") if isinstance(item, dict) else None)
            cnt = getattr(item, "count", 1) or (item.get("count", 1) if isinstance(item, dict) else 1)
            if cat and cat != "Uncategorized":
                category_weights[cat] += cnt

        if category_weights:
            most_common = category_weights.most_common(2)
            # If clear winner
            if len(most_common) == 1 or most_common[0][1] > most_common[1][1]:
                return most_common[0][0]

    # 2. Tie-breaker or no detections: Use CLIP zero-shot classification
    if image_path and image_path.exists() and clip_embedder is not None:
        try:
            scenes_cfg = load_scenes_config()
            canonical_cats = scenes_cfg.get("canonical_categories") or [
                "Nature",
                "Animals",
                "Vehicles",
                "Technology",
                "Food",
                "Architecture",
                "Human activities",
                "Sports",
                "Electronics",
            ]
            best_cat, score = clip_embedder.zero_shot_classify(image_path, canonical_cats)
            logger.info("Zero-shot CLIP assigned category '%s' (score: %.3f)", best_cat, score)
            return best_cat
        except Exception as exc:
            logger.warning("CLIP zero-shot category assignment failed: %s", exc)

    return "Nature"
