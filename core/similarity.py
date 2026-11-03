"""Reverse visual similarity engine for PixelMind.

Calculates multi-modal visual similarity across four selectable dimensions:
1. Object Similarity: Generalized Jaccard index over detected object labels and counts.
2. Colour Similarity: Palette Euclidean distance across top-5 dominant RGB color clusters.
3. Scene Similarity: Categorical alignment across scene classification and indoor/outdoor setting.
4. Overall Similarity: Cosine similarity of 512-dimensional CLIP latent embeddings.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
import numpy as np


def compute_object_similarity(
    query_detections: List[Any],
    target_detections: List[Any],
) -> float:
    """Calculate Jaccard similarity between two sets of detected object labels and counts."""
    if not query_detections and not target_detections:
        return 1.0
    if not query_detections or not target_detections:
        return 0.0

    q_map: Dict[str, int] = {}
    for d in query_detections:
        lbl = (getattr(d, "label", None) or (d.get("label") if isinstance(d, dict) else "")).lower()
        cnt = getattr(d, "count", 1) or (d.get("count", 1) if isinstance(d, dict) else 1)
        if lbl:
            q_map[lbl] = q_map.get(lbl, 0) + cnt

    t_map: Dict[str, int] = {}
    for d in target_detections:
        lbl = (getattr(d, "label", None) or (d.get("label") if isinstance(d, dict) else "")).lower()
        cnt = getattr(d, "count", 1) or (d.get("count", 1) if isinstance(d, dict) else 1)
        if lbl:
            t_map[lbl] = t_map.get(lbl, 0) + cnt

    all_keys = set(q_map.keys()).union(set(t_map.keys()))
    if not all_keys:
        return 0.0

    intersection_sum = 0
    union_sum = 0
    for k in all_keys:
        val_q = q_map.get(k, 0)
        val_t = t_map.get(k, 0)
        intersection_sum += min(val_q, val_t)
        union_sum += max(val_q, val_t)

    return round(float(intersection_sum / union_sum), 3) if union_sum > 0 else 0.0


def compute_color_similarity(
    query_colors: List[Dict[str, Any]],
    target_colors: List[Dict[str, Any]],
) -> float:
    """Calculate color palette similarity based on weighted Euclidean distances in RGB space."""
    if not query_colors or not target_colors:
        return 0.0

    max_dist = math.sqrt(3 * (255.0 ** 2))  # ~441.67
    min_len = min(len(query_colors), len(target_colors))

    weighted_sim = 0.0
    total_weight = 0.0

    for i in range(min_len):
        rgb_q = query_colors[i].get("rgb", [0, 0, 0])
        rgb_t = target_colors[i].get("rgb", [0, 0, 0])
        weight_q = float(query_colors[i].get("percentage", 20.0)) / 100.0

        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(rgb_q, rgb_t)))
        sim = max(0.0, 1.0 - (dist / max_dist))
        weighted_sim += sim * weight_q
        total_weight += weight_q

    return round(float(weighted_sim / total_weight), 3) if total_weight > 0 else 0.0


def compute_scene_similarity(
    query_scene: Optional[str],
    query_env: Optional[str],
    target_scene: Optional[str],
    target_env: Optional[str],
) -> float:
    """Calculate scene agreement score based on scene label and environment."""
    score = 0.0
    if query_env and target_env and query_env.lower() == target_env.lower():
        score += 0.4
    if query_scene and target_scene and query_scene.lower() == target_scene.lower():
        score += 0.6
    return round(score, 3)


def compute_overall_similarity(
    query_vec: Optional[np.ndarray],
    target_vec: Optional[np.ndarray],
) -> float:
    """Calculate overall semantic visual similarity using CLIP latent cosine similarity."""
    if query_vec is None or target_vec is None:
        return 0.0
    try:
        dot = float(np.dot(query_vec, target_vec))
        # Rescale [-1, 1] to [0, 1]
        return round(float(max(0.0, min(1.0, (dot + 1.0) / 2.0))), 3)
    except Exception:
        return 0.0
