"""Image validation, hashing, deskewing, denoising, and contrast enhancement.

Implements the computer vision preprocessing stage of the SnapBase automation pipeline.
Supports modular transformations:
- resize
- crop
- grayscale
- denoise
- Gaussian blur
- sharpen
- thresholding (Otsu, adaptive)
- contrast enhancement (CLAHE)
- rotation / orientation correction
- perspective correction (document quad warp)
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    """Ensure image bytes are non-empty, within size limits, and valid format."""
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
    """Calculate the Laplacian variance to detect blurry images."""
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


def apply_sharpen(image: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """Sharpen image edges using an unsharp mask or Laplacian kernel."""
    kernel = np.array([[0, -1, 0], [-1, 4 + strength, -1], [0, -1, 0]])
    return cv2.filter2D(image, -1, kernel)


def apply_threshold(
    gray_image: np.ndarray, method: str = "otsu"
) -> np.ndarray:
    """Apply binary or adaptive thresholding."""
    if method == "otsu":
        return cv2.threshold(
            gray_image, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
        )[1]
    elif method == "adaptive":
        return cv2.adaptiveThreshold(
            gray_image,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2,
        )
    return gray_image


def apply_perspective_correction(image: np.ndarray) -> np.ndarray:
    """Detect prominent quadrilateral document boundary and apply 4-point perspective warp."""
    orig = image.copy()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 75, 200)

    contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    doc_cnt = None
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            doc_cnt = approx
            break

    if doc_cnt is None:
        return image

    pts = doc_cnt.reshape(4, 2).astype("float32")
    # Order points: top-left, top-right, bottom-right, bottom-left
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    (tl, tr, br, bl) = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    if maxWidth < 100 or maxHeight < 100:
        return image

    dst = np.array(
        [[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]],
        dtype="float32",
    )
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(orig, M, (maxWidth, maxHeight))


def apply_custom_enhancements(
    image_bytes: bytes,
    rotate_deg: float = 0.0,
    grayscale: bool = True,
    denoise: bool = True,
    gaussian_blur: bool = False,
    sharpen: bool = False,
    threshold_method: str = "none",  # 'none', 'otsu', 'adaptive'
    clahe: bool = True,
    perspective: bool = False,
    crop_box: Optional[List[int]] = None,  # [ymin, xmin, ymax, xmax]
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Configurable image enhancement pipeline for the Image Processing playground."""
    pil_img = Image.open(io.BytesIO(image_bytes))
    pil_img = correct_exif_orientation(pil_img)
    if rotate_deg != 0.0:
        pil_img = pil_img.rotate(-rotate_deg, expand=True)

    img = cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)

    # Crop if specified
    if crop_box and len(crop_box) == 4:
        h, w = img.shape[:2]
        y1, x1, y2, x2 = crop_box
        y1, y2 = max(0, min(y1, h)), max(0, min(y2, h))
        x1, x2 = max(0, min(x1, w)), max(0, min(x2, w))
        if y2 > y1 and x2 > x1:
            img = img[y1:y2, x1:x2]

    # Perspective warp
    if perspective:
        img = apply_perspective_correction(img)

    # Resize to standard bounds
    img = resize_image(img)

    # Grayscale
    if grayscale and len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    is_gray = len(img.shape) == 2 or img.shape[2] == 1
    gray_for_stats = img if is_gray else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    is_blurry, blur_score = check_blurriness(gray_for_stats)

    # Denoise
    if denoise:
        if is_gray:
            img = cv2.fastNlMeansDenoising(img, None, 10, 7, 21)
        else:
            img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)

    # Gaussian Blur
    if gaussian_blur:
        img = cv2.GaussianBlur(img, (3, 3), 0)

    # Sharpen
    if sharpen:
        img = apply_sharpen(img, strength=1.2)

    # CLAHE
    if clahe and is_gray:
        img = enhance_contrast(img)

    # Thresholding
    if threshold_method in ("otsu", "adaptive") and is_gray:
        img = apply_threshold(img, method=threshold_method)

    metadata = {
        "width": img.shape[1],
        "height": img.shape[0],
        "is_blurry": is_blurry,
        "blur_score": blur_score,
        "is_grayscale": is_gray,
    }
    return img, metadata


def preprocess_image(
    image_bytes: bytes, output_path: Path
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Default automated preprocessing with optimal defaults that protect OCR accuracy."""
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        pil_img = correct_exif_orientation(pil_img)
        rgb_arr = np.array(pil_img.convert("RGB"))
        bgr_arr = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)

        resized = resize_image(bgr_arr)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        is_blurry, blur_score = check_blurriness(gray)

        deskewed = auto_deskew(gray)
        denoised = cv2.GaussianBlur(deskewed, (3, 3), 0)
        enhanced = enhance_contrast(denoised)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), enhanced)

        metadata: Dict[str, Any] = {
            "width": enhanced.shape[1],
            "height": enhanced.shape[0],
            "blur_score": blur_score,
            "is_blurry": is_blurry,
            "output_path": str(output_path),
        }
        return enhanced, metadata
    except Exception as exc:
        raise PreprocessError(f"Image preprocessing failed: {exc}") from exc
