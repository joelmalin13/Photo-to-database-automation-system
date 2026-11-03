"""Image DNA extraction module for PixelMind.

Generates the multi-dimensional visual fingerprint of an image:
- Top 5 dominant colors with percentages, RGB, and HEX codes (via K-Means)
- Perceptual hash (dHash) for visual similarity
- Cryptographic SHA-256 hash for duplicate blocking
- Structural composition summary (aspect ratio, density, object distribution)
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple
import cv2
import numpy as np
from PIL import Image


def compute_sha256(image_bytes: bytes) -> str:
    """Compute cryptographic SHA-256 hash from raw image bytes."""
    return hashlib.sha256(image_bytes).hexdigest()


def compute_phash(pil_image: Image.Image) -> str:
    """Compute 64-bit difference hash (dHash) for perceptual visual similarity."""
    # Resize to 9x8 grayscale
    resized = pil_image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = np.array(resized)

    # Compare adjacent pixels horizontally: difference between adjacent columns
    diff = pixels[:, 1:] > pixels[:, :-1]

    # Convert binary boolean matrix to 64-bit integer, then to hex string
    decimal_val = 0
    for bit in diff.flatten():
        decimal_val = (decimal_val << 1) | int(bit)

    return f"{decimal_val:016x}"


def compute_phash_distance(phash1: str, phash2: str) -> int:
    """Compute Hamming distance between two 64-bit hex perceptual hashes."""
    if not phash1 or not phash2 or len(phash1) != 16 or len(phash2) != 16:
        return 64
    val1 = int(phash1, 16)
    val2 = int(phash2, 16)
    return bin(val1 ^ val2).count("1")


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB integers to 6-character hexadecimal color string."""
    return f"#{r:02X}{g:02X}{b:02X}"


def extract_dominant_colors(
    pil_image: Image.Image, num_colors: int = 5
) -> List[Dict[str, Any]]:
    """Extract top dominant colors using K-Means clustering on downsampled RGB pixels."""
    # Downsample for sub-50ms execution speed
    thumb = pil_image.convert("RGB").resize((120, 120), Image.Resampling.BILINEAR)
    img_data = np.array(thumb, dtype=np.float32)
    pixels = img_data.reshape(-1, 3)

    # OpenCV K-Means parameters
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 0.2)
    k = min(num_colors, len(pixels))

    try:
        _, labels, centers = cv2.kmeans(
            pixels, k, None, criteria, 5, cv2.KMEANS_PP_CENTERS
        )
        labels = labels.flatten()
        total_pixels = len(labels)

        # Count cluster assignments
        counts = np.bincount(labels, minlength=k)
        sorted_indices = np.argsort(counts)[::-1]

        results: List[Dict[str, Any]] = []
        for idx in sorted_indices[:num_colors]:
            r, g, b = int(round(centers[idx][0])), int(round(centers[idx][1])), int(round(centers[idx][2]))
            pct = round((float(counts[idx]) / total_pixels) * 100.0, 1)
            results.append(
                {
                    "hex": _rgb_to_hex(r, g, b),
                    "rgb": [r, g, b],
                    "percentage": pct,
                }
            )
        return results

    except Exception:
        # Fallback to simple mean if clustering fails
        mean_rgb = [int(p) for p in np.mean(pixels, axis=0)]
        return [
            {
                "hex": _rgb_to_hex(mean_rgb[0], mean_rgb[1], mean_rgb[2]),
                "rgb": mean_rgb,
                "percentage": 100.0,
            }
        ]


def create_composition_summary(
    width: int,
    height: int,
    detections: List[Any],
) -> Dict[str, Any]:
    """Generate structural image composition summary."""
    aspect_ratio = round(width / height, 2) if height > 0 else 1.0

    orientation = "square"
    if aspect_ratio > 1.15:
        orientation = "landscape"
    elif aspect_ratio < 0.85:
        orientation = "portrait"

    total_objects = 0
    cat_breakdown: Dict[str, int] = {}
    label_breakdown: Dict[str, int] = {}

    for d in detections:
        lbl = getattr(d, "label", None) or (d.get("label") if isinstance(d, dict) else "")
        cat = getattr(d, "category", None) or (d.get("category") if isinstance(d, dict) else "")
        cnt = getattr(d, "count", 1) or (d.get("count", 1) if isinstance(d, dict) else 1)

        total_objects += cnt
        if cat:
            cat_breakdown[cat] = cat_breakdown.get(cat, 0) + cnt
        if lbl:
            label_breakdown[lbl] = label_breakdown.get(lbl, 0) + cnt

    return {
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "orientation": orientation,
        "total_objects": total_objects,
        "category_breakdown": cat_breakdown,
        "label_breakdown": label_breakdown,
        "density": "dense" if total_objects >= 8 else ("moderate" if total_objects >= 3 else "sparse"),
    }
