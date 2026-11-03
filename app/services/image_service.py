"""Image ingestion, visual feature extraction, and lifecycle service for PixelMind.

Coordinates the end-to-end processing pipeline:
- SHA-256 duplicate detection
- YOLOv8n object detection & bounding box rendering
- Image DNA generation (K-Means colors, pHash, CLIP embedding)
- Scene & environment classification
- Statistical anomaly detection
- Relational persistence in MySQL / SQLite
"""

from __future__ import annotations

import io
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from config.settings import (
    ALLOWED_EXTENSIONS,
    CONFIDENCE_THRESHOLD,
    MAX_FILE_SIZE_BYTES,
    UPLOAD_DIR,
    logger,
)
from core.anomaly import check_image_anomaly
from core.categorizer import determine_image_category
from core.detector_base import get_detector
from core.dna import (
    compute_phash,
    compute_sha256,
    create_composition_summary,
    extract_dominant_colors,
)
from core.embedder import ClipEmbedder
from core.exceptions import DuplicateImageError, InvalidImageError
from core.scene import classify_scene
from db.crud import (
    add_detections,
    create_image,
    find_image_by_hash,
    flag_anomaly,
    get_image_by_id,
    list_images,
    log_step,
    set_image_dna,
)
from db.models import Image


class ImageService:
    """Service orchestrating image ingestion, computer vision, and persistence."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def validate_file(self, filename: str, content_length: int, file_bytes: bytes) -> None:
        """Validate file extension, size constraints, and image integrity via Pillow."""
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise InvalidImageError(
                f"Unsupported format '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        if content_length > MAX_FILE_SIZE_BYTES or len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise InvalidImageError("File size exceeds 15 MB limit.")

        if len(file_bytes) == 0:
            raise InvalidImageError("Uploaded file is empty.")

        try:
            with PILImage.open(io.BytesIO(file_bytes)) as img:
                img.verify()
        except Exception as exc:
            raise InvalidImageError(f"Corrupt or invalid image payload: {exc}") from exc

    def ingest_image(
        self,
        filename: str,
        file_bytes: bytes,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ) -> Tuple[Image, bool, str]:
        """Ingest a single photo, run detection and DNA analysis, and persist structured records."""
        start_time = time.time()
        self.validate_file(filename, len(file_bytes), file_bytes)

        # 1. SHA-256 duplicate detection
        sha256_hash = compute_sha256(file_bytes)
        existing = find_image_by_hash(self.db, sha256_hash)
        if existing:
            log_step(
                self.db,
                existing.id,
                "ingest_duplicate_check",
                status="duplicate",
                message=f"Duplicate upload of {filename} matched existing image #{existing.id}.",
            )
            return existing, True, f"Duplicate image already exists in database (ID: #{existing.id})."

        # 2. Save original image with UUID prefix
        safe_filename = f"{uuid.uuid4().hex[:10]}_{Path(filename).name}"
        saved_path = UPLOAD_DIR / safe_filename
        saved_path.write_bytes(file_bytes)

        # 3. Read PIL image for dimensions and DNA
        with PILImage.open(io.BytesIO(file_bytes)) as pil_img:
            width, height = pil_img.size
            phash = compute_phash(pil_img)
            dominant_colors = extract_dominant_colors(pil_img, num_colors=5)

        # 4. Object Detection (YOLOv8n)
        detector = get_detector("yolo")
        detection_res = detector.detect(
            saved_path,
            confidence_threshold=confidence_threshold,
            save_annotated=True,
        )

        # 5. Embedding Generation (CLIP)
        embedder = ClipEmbedder.get_instance()
        embedding_vec = embedder.embed_image(saved_path)
        embedding_blob = embedding_vec.tobytes() if embedding_vec is not None else None

        # 6. Automatic Categorization & Scene Understanding
        category = determine_image_category(detection_res.items, saved_path, embedder)
        scene, environment = classify_scene(saved_path, embedder, detection_res.items)

        # 7. Persist Primary Image Entity
        img = create_image(
            session=self.db,
            filename=filename,
            stored_path=str(saved_path),
            annotated_path=detection_res.annotated_path,
            sha256=sha256_hash,
            phash=phash,
            width=width,
            height=height,
            category=category,
            scene=scene,
            environment=environment,
        )

        # 8. Persist Detections
        detections_payload = [
            {
                "label": item.label,
                "category": item.category,
                "count": item.count,
                "avg_confidence": item.avg_confidence,
                "bboxes": item.bboxes,
            }
            for item in detection_res.items
        ]
        add_detections(self.db, img.id, detections_payload)

        # 9. Persist Image DNA
        composition = create_composition_summary(width, height, detection_res.items)
        set_image_dna(
            session=self.db,
            image_id=img.id,
            dominant_colors=dominant_colors,
            embedding_blob=embedding_blob,
            composition=composition,
        )

        # 10. Statistical Anomaly Flagging
        anomaly_check = check_image_anomaly(detection_res.items)
        if anomaly_check:
            reason, score = anomaly_check
            flag_anomaly(self.db, img.id, reason, score)

        duration_ms = int((time.time() - start_time) * 1000)
        log_step(
            self.db,
            img.id,
            "full_ingestion_pipeline",
            status="success",
            message=f"Detected {detection_res.total_count} objects in {len(detection_res.items)} classes.",
            execution_time_ms=duration_ms,
        )

        logger.info("Successfully ingested image #%d: %s (%d ms)", img.id, filename, duration_ms)
        return img, False, "Image processed and stored successfully."

    def get_image(self, image_id: int) -> Optional[Image]:
        """Fetch single image entity by ID."""
        return get_image_by_id(self.db, image_id)

    def list_gallery(
        self,
        category: Optional[str] = None,
        label: Optional[str] = None,
        environment: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 12,
    ) -> Tuple[List[Image], int]:
        """Retrieve paginated images for the gallery view."""
        return list_images(
            session=self.db,
            category=category,
            label=label,
            environment=environment,
            search=search,
            page=page,
            page_size=page_size,
        )
