"""Unit tests for Image DNA extraction, dominant colors, perceptual hashing, and SHA-256.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from core.dna import (
    compute_phash,
    compute_phash_distance,
    compute_sha256,
    create_composition_summary,
    extract_dominant_colors,
)
from core.detector_base import DetectionItem


def test_compute_sha256():
    """Verify SHA-256 produces 64-char lowercase hex string and matches identical content."""
    data = b"PixelMind AI Visual Intelligence Database"
    hash1 = compute_sha256(data)
    hash2 = compute_sha256(data)
    assert len(hash1) == 64
    assert hash1 == hash2

    diff_hash = compute_sha256(b"Different image bytes")
    assert hash1 != diff_hash


def test_compute_phash_identical_and_similar():
    """Verify perceptual hash (dHash) gives distance 0 for identical images and low for similar."""
    img1 = Image.new("RGB", (100, 100), color=(255, 0, 0))
    phash1 = compute_phash(img1)
    assert len(phash1) == 16

    # Identical image
    phash2 = compute_phash(img1)
    assert compute_phash_distance(phash1, phash2) == 0

    # Slight variation
    img_slight = Image.new("RGB", (100, 100), color=(250, 5, 5))
    phash_slight = compute_phash(img_slight)
    dist = compute_phash_distance(phash1, phash_slight)
    assert dist <= 5


def test_extract_dominant_colors():
    """Verify K-Means extracts top 5 dominant colors with hex, rgb, and percentages."""
    # Create an image half red and half blue
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    for x in range(50):
        for y in range(100):
            img.putpixel((x, y), (0, 0, 255))

    colors = extract_dominant_colors(img, num_colors=2)
    assert len(colors) == 2
    for c in colors:
        assert "hex" in c
        assert "rgb" in c
        assert "percentage" in c
        assert c["hex"].startswith("#")
        assert len(c["rgb"]) == 3
        assert 0.0 <= c["percentage"] <= 100.0


def test_create_composition_summary():
    """Verify composition summary computation."""
    detections = [
        DetectionItem(label="car", category="Vehicles", count=2, avg_confidence=0.9),
        DetectionItem(label="person", category="Human activities", count=1, avg_confidence=0.85),
    ]
    summary = create_composition_summary(1920, 1080, detections)
    assert summary["width"] == 1920
    assert summary["height"] == 1080
    assert summary["aspect_ratio"] == 1.78
    assert summary["orientation"] == "landscape"
    assert summary["total_objects"] == 3
    assert len(summary["label_breakdown"]) == 2
    assert summary["density"] == "moderate"
