"""Unit tests for automatic category determination and label-to-category mapping.
"""

from __future__ import annotations

from core.categorizer import get_label_category, determine_image_category
from core.detector_base import DetectionItem


def test_label_to_category_mapping():
    """Verify common labels map to their configured canonical categories."""
    assert get_label_category("car") == "Vehicles"
    assert get_label_category("truck") == "Vehicles"
    assert get_label_category("dog") == "Animals"
    assert get_label_category("cat") == "Animals"
    assert get_label_category("person") == "Human activities"
    assert get_label_category("laptop") == "Electronics"
    assert get_label_category("tv") == "Electronics"
    assert get_label_category("pizza") == "Food"
    assert get_label_category("bench") == "Architecture"


def test_determine_image_category_single_dominant():
    """Verify category determined by single dominant detected object class."""
    items = [
        DetectionItem(label="car", category="Vehicles", count=3, avg_confidence=0.88),
        DetectionItem(label="person", category="Human activities", count=1, avg_confidence=0.92),
    ]
    category = determine_image_category(items)
    assert category == "Vehicles"


def test_determine_image_category_animal_dominant():
    """Verify category determined when animals are dominant."""
    items = [
        DetectionItem(label="dog", category="Animals", count=2, avg_confidence=0.95),
        DetectionItem(label="cat", category="Animals", count=1, avg_confidence=0.91),
        DetectionItem(label="chair", category="Architecture", count=1, avg_confidence=0.60),
    ]
    category = determine_image_category(items)
    assert category == "Animals"


def test_determine_image_category_empty_fallback():
    """Verify fallback to Technology/default when no detections or embedder provided."""
    category = determine_image_category([])
    assert category in ["Nature", "Technology", "Architecture", "Food"]
