"""Unit tests for reverse visual similarity across all 4 modes.
"""

from __future__ import annotations

import numpy as np
from core.similarity import (
    compute_color_similarity,
    compute_object_similarity,
    compute_overall_similarity,
    compute_scene_similarity,
)


def test_object_similarity_exact_and_disjoint():
    """Verify Jaccard calculation on object sets."""
    d1 = [{"label": "car", "count": 2}, {"label": "person", "count": 1}]
    d2 = [{"label": "car", "count": 2}, {"label": "person", "count": 1}]
    assert compute_object_similarity(d1, d2) == 1.0

    d3 = [{"label": "dog", "count": 1}]
    assert compute_object_similarity(d1, d3) == 0.0

    # Partial overlap
    d4 = [{"label": "car", "count": 1}]
    sim = compute_object_similarity(d1, d4)
    assert 0.0 < sim < 1.0


def test_color_similarity():
    """Verify color palette similarity using weighted Euclidean distance."""
    c1 = [{"hex": "#FF0000", "rgb": [255, 0, 0], "percentage": 100.0}]
    c2 = [{"hex": "#FF0000", "rgb": [255, 0, 0], "percentage": 100.0}]
    assert compute_color_similarity(c1, c2) == 1.0

    c3 = [{"hex": "#0000FF", "rgb": [0, 0, 255], "percentage": 100.0}]
    assert compute_color_similarity(c1, c3) < 0.6


def test_scene_similarity():
    """Verify scene alignment score."""
    # Both match
    assert compute_scene_similarity("street", "outdoor", "street", "outdoor") == 1.0

    # Only environment matches
    assert compute_scene_similarity("park", "outdoor", "street", "outdoor") == 0.4

    # Neither matches
    assert compute_scene_similarity("office", "indoor", "forest", "outdoor") == 0.0


def test_overall_similarity():
    """Verify normalized cosine similarity for CLIP vectors."""
    v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    assert compute_overall_similarity(v1, v2) == 1.0

    v3 = np.array([-1.0, 0.0, 0.0], dtype=np.float32)
    assert compute_overall_similarity(v1, v3) == 0.0
