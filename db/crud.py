"""Parameterized database CRUD operations and lifecycle management for PixelMind.

All queries are parameterized to prevent SQL injection and maintain strict relational integrity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from db.models import (
    Anomaly,
    Detection,
    Image,
    ImageDNA,
    ProcessingLog,
)


def log_step(
    session: Session,
    image_id: Optional[int],
    step: str,
    status: str = "success",
    message: Optional[str] = None,
    execution_time_ms: int = 0,
) -> ProcessingLog:
    """Record an audit log entry in processing_log."""
    log_entry = ProcessingLog(
        image_id=image_id,
        step=step,
        status=status,
        message=message,
        execution_time_ms=execution_time_ms,
    )
    session.add(log_entry)
    return log_entry


def create_image(
    session: Session,
    filename: str,
    stored_path: str,
    annotated_path: Optional[str],
    sha256: str,
    phash: Optional[str],
    width: int,
    height: int,
    category: str = "Uncategorized",
    scene: Optional[str] = None,
    environment: Optional[str] = None,
    status: str = "done",
    caption: Optional[str] = None,
) -> Image:
    """Insert a new image record into the database."""
    img = Image(
        filename=filename,
        stored_path=stored_path,
        annotated_path=annotated_path,
        sha256=sha256,
        phash=phash,
        width=width,
        height=height,
        category=category,
        scene=scene,
        environment=environment,
        status=status,
        caption=caption,
    )
    session.add(img)
    session.flush()
    return img


def find_image_by_hash(session: Session, sha256_hash: str) -> Optional[Image]:
    """Look up an existing image by SHA-256 hash for duplicate detection."""
    stmt = select(Image).where(Image.sha256 == sha256_hash)
    return session.scalar(stmt)


def add_detections(
    session: Session,
    image_id: int,
    detections_list: List[Dict[str, Any]],
) -> List[Detection]:
    """Insert YOLO detections for an image."""
    records: List[Detection] = []
    for item in detections_list:
        rec = Detection(
            image_id=image_id,
            label=item["label"],
            category=item["category"],
            count=item.get("count", 1),
            avg_confidence=float(item.get("avg_confidence", 0.0)),
            bbox_json=item.get("bboxes", []),
        )
        session.add(rec)
        records.append(rec)
    session.flush()
    return records


def set_image_dna(
    session: Session,
    image_id: int,
    dominant_colors: List[Dict[str, Any]],
    embedding_vector: Optional[Any],
    composition: Dict[str, Any],
) -> ImageDNA:
    """Store or update the visual fingerprint and DNA of an image with JSON embedding."""
    dna = session.get(ImageDNA, image_id)
    if not dna:
        dna = ImageDNA(image_id=image_id)
        session.add(dna)

    dna.dominant_colors_json = dominant_colors
    dna.composition_json = composition

    # Normalize embedding to JSON list of floats
    if embedding_vector is not None:
        if isinstance(embedding_vector, list):
            dna.embedding_json = [float(x) for x in embedding_vector]
        elif isinstance(embedding_vector, np.ndarray):
            dna.embedding_json = embedding_vector.astype(float).tolist()
        elif isinstance(embedding_vector, bytes):
            dna.embedding_blob = embedding_vector
            try:
                arr = np.frombuffer(embedding_vector, dtype=np.float32)
                dna.embedding_json = arr.astype(float).tolist()
            except Exception:
                pass
    session.flush()
    return dna


def flag_anomaly(
    session: Session,
    image_id: int,
    reason: str,
    score: float,
) -> Anomaly:
    """Record statistical anomaly flag for an image."""
    anom = session.get(Anomaly, image_id)
    if not anom:
        anom = Anomaly(image_id=image_id)
        session.add(anom)
    anom.reason = reason
    anom.score = score
    session.flush()
    return anom


def get_image_by_id(session: Session, image_id: int) -> Optional[Image]:
    """Retrieve image entity by primary key."""
    return session.get(Image, image_id)


def delete_image(session: Session, image_id: int) -> bool:
    """Delete image and all cascading child records."""
    img = session.get(Image, image_id)
    if not img:
        return False
    session.delete(img)
    session.flush()
    return True


def list_images(
    session: Session,
    category: Optional[str] = None,
    label: Optional[str] = None,
    environment: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 12,
) -> Tuple[List[Image], int]:
    """Search, filter, sort, and paginate image records."""
    stmt = select(Image)

    if category and category.lower() != "all":
        stmt = stmt.where(Image.category.ilike(category))

    if environment and environment.lower() != "all":
        stmt = stmt.where(Image.environment.ilike(environment))

    if label and label.lower() != "all":
        stmt = stmt.join(Image.detections).where(Detection.label.ilike(f"%{label}%"))

    if search:
        search_pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Image.filename.ilike(search_pattern),
                Image.category.ilike(search_pattern),
                Image.scene.ilike(search_pattern),
                Image.detections.any(Detection.label.ilike(search_pattern)),
            )
        )

    # Count total matching
    count_stmt = select(func.count()).select_from(stmt.distinct().subquery())
    total = session.scalar(count_stmt) or 0

    # Sorting
    sort_column = getattr(Image, sort_by, Image.created_at)
    if sort_order.lower() == "desc":
        stmt = stmt.order_by(desc(sort_column))
    else:
        stmt = stmt.order_by(sort_column)

    # Pagination
    offset = max(0, (page - 1) * page_size)
    stmt = stmt.distinct().offset(offset).limit(page_size)

    items = list(session.scalars(stmt).all())
    return items, total


def get_all_embeddings(session: Session) -> List[Tuple[int, np.ndarray]]:
    """Retrieve all stored embeddings as numpy float32 arrays, supporting both JSON and legacy blobs."""
    stmt = select(ImageDNA.image_id, ImageDNA.embedding_json, ImageDNA.embedding_blob).where(
        or_(ImageDNA.embedding_json.isnot(None), ImageDNA.embedding_blob.isnot(None))
    )
    rows = session.execute(stmt).all()
    results: List[Tuple[int, np.ndarray]] = []
    for img_id, emb_json, blob in rows:
        if emb_json:
            try:
                arr = np.array(emb_json, dtype=np.float32)
                results.append((img_id, arr))
                continue
            except Exception:
                pass
        if blob:
            try:
                arr = np.frombuffer(blob, dtype=np.float32)
                results.append((img_id, arr))
            except Exception:
                continue
    return results


def get_all_dna_for_similarity(
    session: Session,
) -> List[Tuple[Image, Optional[ImageDNA], List[Detection]]]:
    """Retrieve all images with DNA and detections for reverse similarity search."""
    stmt = select(Image)
    images = list(session.scalars(stmt).all())
    results: List[Tuple[Image, Optional[ImageDNA], List[Detection]]] = []
    for img in images:
        results.append((img, img.dna, img.detections or []))
    return results


# -------------------------------------------------------------
# Parameterized Query Engine for "Ask Your Images"
# -------------------------------------------------------------

def count_label_across_all(session: Session, label: str) -> int:
    """Return total count of a specific object detected across all images."""
    stmt = select(func.sum(Detection.count)).where(Detection.label.ilike(label))
    result = session.scalar(stmt)
    return int(result or 0)


def find_images_with_label(session: Session, label: str) -> List[Image]:
    """Find images containing a specific detected label."""
    stmt = select(Image).join(Image.detections).where(Detection.label.ilike(label)).distinct()
    return list(session.scalars(stmt).all())


def find_images_with_both_labels(session: Session, label_a: str, label_b: str) -> List[Image]:
    """Find images containing both specified object labels."""
    stmt = (
        select(Image)
        .where(
            Image.detections.any(Detection.label.ilike(label_a)),
            Image.detections.any(Detection.label.ilike(label_b)),
        )
        .distinct()
    )
    return list(session.scalars(stmt).all())


def find_image_with_max_objects(session: Session) -> Optional[Tuple[Image, int]]:
    """Find the single image containing the highest total object count."""
    subq = (
        select(Detection.image_id, func.sum(Detection.count).label("total_objs"))
        .group_by(Detection.image_id)
        .order_by(desc("total_objs"))
        .limit(1)
        .subquery()
    )
    stmt = select(Image, subq.c.total_objs).join(subq, Image.id == subq.c.image_id)
    row = session.execute(stmt).first()
    if row:
        return row[0], int(row[1])
    return None


def find_compound_images(
    session: Session,
    environment: Optional[str],
    min_vehicles: int = 0,
    min_persons: int = 0,
) -> List[Image]:
    """Find outdoor images containing minimum counts of vehicles and persons."""
    stmt = select(Image)
    if environment:
        stmt = stmt.where(Image.environment.ilike(environment))

    candidate_images = list(session.scalars(stmt).all())
    matching: List[Image] = []
    for img in candidate_images:
        vehicle_count = sum(
            d.count for d in img.detections if d.category == "Vehicles"
        )
        person_count = sum(
            d.count for d in img.detections if d.label.lower() in ("person", "people")
        )
        if vehicle_count >= min_vehicles and person_count >= min_persons:
            matching.append(img)
    return matching


def find_images_by_category(session: Session, category: str) -> List[Image]:
    """Find all images classified under or containing detections of a category."""
    stmt = (
        select(Image)
        .where(
            or_(
                Image.category.ilike(f"%{category}%"),
                Image.detections.any(Detection.category.ilike(f"%{category}%")),
            )
        )
        .distinct()
    )
    return list(session.scalars(stmt).all())


# -------------------------------------------------------------
# Analytics Aggregation Engine
# -------------------------------------------------------------

def get_analytics_summary(session: Session) -> Dict[str, Any]:
    """Aggregate real database metrics for Chart.js visualizations."""
    total_images = session.scalar(select(func.count(Image.id))) or 0
    total_objects = session.scalar(select(func.sum(Detection.count))) or 0
    total_anomalies = session.scalar(select(func.count(Anomaly.image_id))) or 0

    # Top detected objects
    top_obj_rows = (
        session.query(Detection.label, func.sum(Detection.count).label("total"))
        .group_by(Detection.label)
        .order_by(desc("total"))
        .limit(8)
        .all()
    )
    top_objects = {
        "labels": [r[0] for r in top_obj_rows],
        "counts": [int(r[1]) for r in top_obj_rows],
    }

    # Category distribution
    cat_rows = (
        session.query(Image.category, func.count(Image.id).label("total"))
        .group_by(Image.category)
        .order_by(desc("total"))
        .all()
    )
    category_dist = {
        "labels": [r[0] for r in cat_rows],
        "counts": [int(r[1]) for r in cat_rows],
    }

    # Environment distribution (Indoor vs Outdoor)
    env_rows = (
        session.query(Image.environment, func.count(Image.id))
        .group_by(Image.environment)
        .all()
    )
    env_dist = {
        "labels": [r[0] or "Unknown" for r in env_rows],
        "counts": [int(r[1]) for r in env_rows],
    }

    # Scene distribution
    scene_rows = (
        session.query(Image.scene, func.count(Image.id).label("total"))
        .group_by(Image.scene)
        .order_by(desc("total"))
        .limit(6)
        .all()
    )
    scene_dist = {
        "labels": [r[0] or "General" for r in scene_rows],
        "counts": [int(r[1]) for r in scene_rows],
    }

    # Monthly upload trend
    dialect_name = ""
    try:
        bind = session.get_bind()
        if bind and bind.dialect:
            dialect_name = bind.dialect.name
    except Exception:
        dialect_name = "sqlite"

    month_col = (
        func.strftime("%Y-%m", Image.created_at)
        if "sqlite" in dialect_name
        else func.date_format(Image.created_at, "%Y-%m")
    )
    trend_rows = (
        session.query(month_col.label("month_str"), func.count(Image.id))
        .group_by(month_col)
        .order_by(month_col)
        .limit(12)
        .all()
    )
    monthly_trend = {
        "labels": [str(r[0]) for r in trend_rows] if trend_rows else ["Current Month"],
        "counts": [int(r[1]) for r in trend_rows] if trend_rows else [total_images],
    }

    return {
        "has_data": total_images > 0,
        "total_images": total_images,
        "total_objects": int(total_objects),
        "total_anomalies": total_anomalies,
        "top_objects": top_objects,
        "category_dist": category_dist,
        "env_dist": env_dist,
        "scene_dist": scene_dist,
        "monthly_trend": monthly_trend,
    }
