"""Image validation, hashing, deskewing, denoising, and contrast enhancement.

Implements the preprocessing stage of the SnapBase automation pipeline.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any, Dict, Tuple

import cv2
import numpy as np
from PIL import ExifTags, Image

from config.settings import (
    ALLOWED_EXTENSIONS,
    MAX_IMAGE_SIZE_BYTES,
    logger,
)
from core.exceptions import PreprocessError, ValidationError


def compute_image_hash(image_bytes: bytes) -> str:
    """Compute the SHA-256 cryptographic hash of image bytes."""
    return hashlib.sha256(image_bytes).hexdigest()


def validate_image_bytes(
    image_bytes: bytes, filename: str = "upload.jpg"
) -> None:
    """Ensure image bytes are non-empty, within size limits, and valid format.

    Args:
        image_bytes: Raw binary payload of the uploaded image.
        filename: Name of the uploaded file.

    Raises:
        ValidationError: If the file is invalid, corrupt, or oversized.
    """
    if not image_bytes:
        raise ValidationError("Uploaded file is empty (0 bytes).")

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        mb_size = len(image_bytes) / (1024 * 1024)
        raise ValidationError(
            f"File size ({mb_size:.1f} MB) exceeds maximum allowed 10 MB limit."
        )

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file format '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    try:
        with Image.open(io.BytesIO(image_bytes)) as pil_img:
            pil_img.verify()
    except Exception as exc:
        raise ValidationError(f"Corrupt or unreadable image file: {exc}") from exc


def check_blurriness(
    gray_image: np.ndarray, threshold: float = 60.0
) -> Tuple[bool, float]:
    """Calculate the Laplacian variance to detect blurry images.

    Args:
        gray_image: Grayscale numpy array of the image.
        threshold: Variance threshold below which image is marked blurry.

    Returns:
        Tuple[bool, float]: (is_blurry, variance_score)
    """
    score = float(cv2.Laplacian(gray_image, cv2.CV_64F).var())
    return score < threshold, round(score, 2)


def correct_exif_orientation(pil_image: Image.Image) -> Image.Image:
    """Rotate PIL image according to its EXIF orientation tag."""
    try:
        exif = pil_image.getexif()
        orientation_key = next(
            (k for k, v in ExifTags.TAGS.items() if v == "Orientation"), None
        )
        if orientation_key and orientation_key in exif:
            orientation = exif[orientation_key]
            rotations = {3: 180, 6: 270, 8: 90}
            if orientation in rotations:
                return pil_image.rotate(rotations[orientation], expand=True)
    except Exception as exc:
        logger.debug("Failed EXIF orientation check: %s", exc)
    return pil_image


def resize_image(image: np.ndarray, max_dim: int = 1800) -> np.ndarray:
    """Scale down large images to stay within memory and latency bounds."""
    height, width = image.shape[:2]
    if max(height, width) <= max_dim:
        return image
    scaling = max_dim / float(max(height, width))
    new_w = int(width * scaling)
    new_h = int(height * scaling)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def auto_deskew(gray_image: np.ndarray) -> np.ndarray:
    """Detect and correct document skew using minimum bounding rectangle."""
    thresh = cv2.threshold(
        gray_image, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )[1]
    coords = np.column_stack(np.where(thresh > 0))
    if coords.size == 0:
        return gray_image

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    elif angle > 45:
        angle = 90 - angle

    # Only correct subtle document skew between 0.5 and 45 degrees
    if abs(angle) > 0.5 and abs(angle) < 45.0:
        h, w = gray_image.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            gray_image,
            matrix,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
    return gray_image


def enhance_contrast(gray_image: np.ndarray) -> np.ndarray:
    """Apply adaptive histogram equalization (CLAHE) for OCR clarity."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray_image)


def preprocess_image(
    image_bytes: bytes, output_path: Path
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Execute complete preprocessing pipeline: validate, rotate, resize, denoise, enhance.

    Args:
        image_bytes: Raw input bytes of the document photo.
        output_path: Target filesystem location to persist the enhanced image.

    Returns:
        Tuple[np.ndarray, Dict[str, Any]]: (processed_img_array, metadata)
    """
    try:
        # Load through PIL to handle EXIF
        pil_img = Image.open(io.BytesIO(image_bytes))
        pil_img = correct_exif_orientation(pil_img)
        # Convert to BGR array for OpenCV
        rgb_arr = np.array(pil_img.convert("RGB"))
        bgr_arr = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)

        # Resize
        resized = resize_image(bgr_arr)

        # Grayscale
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

        # Blur check
        is_blurry, blur_score = check_blurriness(gray)

        # Deskew
        deskewed = auto_deskew(gray)

        # Denoise (Gaussian)
        denoised = cv2.GaussianBlur(deskewed, (3, 3), 0)

        # Contrast enhancement
        enhanced = enhance_contrast(denoised)

        # Save preprocessed image to disk
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), enhanced)

        metadata: Dict[str, Any] = {
            "width": enhanced.shape[1],
            "height": enhanced.shape[0],
            "blur_score": blur_score,
            "is_blurry": is_blurry,
            "output_path": str(output_path),
        }
        logger.info(
            "Preprocessed image saved to %s (blur_score=%.1f)",
            output_path.name,
            blur_score,
        )
        return enhanced, metadata
    except Exception as exc:
        raise PreprocessError(f"Image preprocessing failed: {exc}") from exc
