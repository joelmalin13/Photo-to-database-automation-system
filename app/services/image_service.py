"""Image ingestion, visual feature extraction, and lifecycle service for PixelMind.

Coordinates the end-to-end processing pipeline in both Cloud and Local modes:
- SHA-256 duplicate detection
- Storage persistence (LocalStorage / Supabase Cloud Storage)
- Object detection & bounding box rendering (Gemini 2.5 Flash / YOLOv8n)
- Image DNA generation (Pure NumPy K-Means colors, pHash, JSON embedding)
- Scene & environment classification
- Statistical anomaly detection
- Relational persistence in PostgreSQL / MySQL / SQLite
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
    AI_MODE,
    ALLOWED_EXTENSIONS,
    CONFIDENCE_THRESHOLD,
    MAX_FILE_SIZE_BYTES,
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
from core.embedder import get_embedder
from core.exceptions import DetectionError, DuplicateImageError, InvalidImageError
from core.scene import classify_scene
from core.storage import get_storage
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
        self.storage = get_storage()

    def validate_file(self, filename: str, content_length: int, file_bytes: bytes) -> None:
        """Validate file extension, size constraints, and image integrity via Pillow."""
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise InvalidImageError(
                f"Unsupported format '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        if content_length > MAX_FILE_SIZE_BYTES or len(file_bytes) > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
            raise InvalidImageError(f"File size exceeds the {max_mb} MB limit for this environment.")

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

        # 2. Persist original image to configured storage (Local or Supabase)
        stored_path, access_url = self.storage.save_file(file_bytes, filename, is_annotated=False)

        # 3. Read PIL image for dimensions and Image DNA
        with PILImage.open(io.BytesIO(file_bytes)) as pil_img:
            width, height = pil_img.size
            phash = compute_phash(pil_img)
            dominant_colors = extract_dominant_colors(pil_img, num_colors=5)

        # 4. Object Detection & Visual Analysis (Gemini in Cloud / YOLO in Local)
        detector = get_detector()
        detection_failed = False
        error_message = ""

        try:
            detection_res = detector.detect(
                file_bytes,
                confidence_threshold=confidence_threshold,
                save_annotated=True,
            )
        except DetectionError as det_err:
            logger.warning("Object detection error on %s: %s", filename, det_err)
            detection_failed = True
            error_message = str(det_err)
        except Exception as exc:
            logger.error("Unexpected detection failure on %s: %s", filename, exc)
            detection_failed = True
            error_message = f"Inference error: {exc}"

        # 5. Handle Failed Ingestion gracefully
        if detection_failed:
            img = create_image(
                session=self.db,
                filename=filename,
                stored_path=access_url,
                annotated_path=None,
                sha256=sha256_hash,
                phash=phash,
                width=width,
                height=height,
                category="Uncategorized",
                status="failed",
                caption=f"Failed: {error_message}",
            )
            log_step(
                self.db,
                img.id,
                "detection",
                status="failed",
                message=error_message,
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
            return img, False, f"Image uploaded but analysis failed ({error_message}). Click Retry to re-process."

        # 6. Save annotated image to storage if rendered
        annotated_url = None
        if getattr(detection_res, "annotated_bytes", None):
            _, annotated_url = self.storage.save_file(
                detection_res.annotated_bytes, f"annotated_{filename}", is_annotated=True
            )
        elif detection_res.annotated_path:
            annotated_url = detection_res.annotated_path

        # 7. Semantic Category & Scene Resolution
        embedder = get_embedder()
        category = detection_res.category or determine_image_category(detection_res.items)
        scene = detection_res.scene or "general"
        environment = detection_res.environment or "outdoor"
        caption = detection_res.caption

        # 8. Embedding Generation (JSON list of floats)
        object_labels = [item.label for item in detection_res.items]
        embedding_vec = embedder.embed_image_metadata(
            image_input=file_bytes,
            caption=caption,
            objects=object_labels,
            scene=scene,
            environment=environment,
        )

        # 9. Persist Primary Image Entity
        img = create_image(
            session=self.db,
            filename=filename,
            stored_path=access_url,
            annotated_path=annotated_url,
            sha256=sha256_hash,
            phash=phash,
            width=width,
            height=height,
            category=category,
            scene=scene,
            environment=environment,
            status="done",
            caption=caption,
        )

        # 10. Persist Detections
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

        # 11. Persist Image DNA
        composition = create_composition_summary(width, height, detection_res.items)
        set_image_dna(
            session=self.db,
            image_id=img.id,
            dominant_colors=dominant_colors,
            embedding_vector=embedding_vec,
            composition=composition,
        )

        # 12. Statistical Anomaly Flagging
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
            message=f"Mode: {AI_MODE}. Detected {detection_res.total_count} objects in {len(detection_res.items)} classes.",
            execution_time_ms=duration_ms,
        )

        logger.info("Successfully ingested image #%d: %s (%d ms)", img.id, filename, duration_ms)
        return img, False, "Image processed and stored successfully."

    def reprocess_image(self, image_id: int) -> Tuple[Optional[Image], str]:
        """Retry processing for a failed or unanalyzed image."""
        img = self.get_image(image_id)
        if not img:
            return None, f"Image #{image_id} not found."

        try:
            file_bytes = self.storage.read_bytes(img.stored_path)
        except Exception as exc:
            return img, f"Could not retrieve stored image bytes: {exc}"

        detector = get_detector()
        try:
            res = detector.detect(file_bytes, confidence_threshold=CONFIDENCE_THRESHOLD, save_annotated=True)
        except Exception as exc:
            return img, f"Retry analysis failed: {exc}"

        # Update annotated image
        if getattr(res, "annotated_bytes", None):
            _, ann_url = self.storage.save_file(res.annotated_bytes, f"annotated_{img.filename}", is_annotated=True)
            img.annotated_path = ann_url

        embedder = get_embedder()
        img.category = res.category or determine_image_category(res.items)
        img.scene = res.scene or "general"
        img.environment = res.environment or "outdoor"
        img.caption = res.caption
        img.status = "done"

        # Update detections
        detections_payload = [
            {"label": it.label, "category": it.category, "count": it.count, "avg_confidence": it.avg_confidence, "bboxes": it.bboxes}
            for it in res.items
        ]
        add_detections(self.db, img.id, detections_payload)

        # Update DNA
        composition = create_composition_summary(img.width, img.height, res.items)
        emb_vec = embedder.embed_image_metadata(
            image_input=file_bytes,
            caption=res.caption,
            objects=[it.label for it in res.items],
            scene=img.scene,
            environment=img.environment,
        )
        with PILImage.open(io.BytesIO(file_bytes)) as p_img:
            colors = extract_dominant_colors(p_img, num_colors=5)

        set_image_dna(self.db, img.id, colors, emb_vec, composition)
        self.db.commit()

        return img, "Image re-analyzed successfully."

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
