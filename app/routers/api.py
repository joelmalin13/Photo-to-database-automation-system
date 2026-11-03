"""OpenAPI-documented REST endpoints for PixelMind visual intelligence platform.

Provides programmatic JSON endpoints for image ingestion, semantic search,
natural language visual Q&A, reverse image similarity, and visual analytics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.analytics_service import AnalyticsService
from app.services.dna_service import DnaService
from app.services.image_service import ImageService
from app.services.search_service import SearchService
from core.exceptions import DuplicateImageError, InvalidImageError
from db.crud import delete_image
from db.session import get_db_status

router = APIRouter(prefix="/api", tags=["Visual Intelligence API"])


# -------------------------------------------------------------
# Request & Response Schemas
# -------------------------------------------------------------

class SearchRequest(BaseModel):
    """Natural language search payload."""
    query: str = Field(..., min_length=1, description="Natural language search query e.g. 'a red car beside a tree'")
    limit: Optional[int] = Field(20, ge=1, le=100)


class AskRequest(BaseModel):
    """Ask Your Images question payload."""
    question: str = Field(..., min_length=1, description="Natural language question about the image database")


# -------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------

@router.post(
    "/images",
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest one or multiple photographs",
)
async def upload_images(
    files: List[UploadFile] = File(...),
    confidence_threshold: float = Form(0.25),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Ingest image files, detect objects with YOLO, compute DNA, and persist records."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided for upload.")

    service = ImageService(db)
    ingested_items: List[Dict[str, Any]] = []
    errors: List[str] = []

    for file in files:
        try:
            content = await file.read()
            img, is_dup, msg = service.ingest_image(
                filename=file.filename or "uploaded.jpg",
                file_bytes=content,
                confidence_threshold=confidence_threshold,
            )
            item_dict = img.to_dict()
            item_dict["is_duplicate"] = is_dup
            item_dict["message"] = msg
            ingested_items.append(item_dict)
        except InvalidImageError as err:
            errors.append(f"{file.filename}: {err.message}")
        except Exception as exc:
            errors.append(f"{file.filename}: Processing failed ({exc})")

    if not ingested_items and errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    return {
        "success": True,
        "processed_count": len(ingested_items),
        "images": ingested_items,
        "errors": errors,
    }


@router.get(
    "/images",
    summary="Search, filter, sort, and paginate stored images",
)
def list_images_endpoint(
    category: Optional[str] = Query(None, description="Filter by category e.g. Vehicles, Animals"),
    label: Optional[str] = Query(None, description="Filter by detected object label e.g. car, person"),
    environment: Optional[str] = Query(None, description="Filter by environment (indoor / outdoor)"),
    search: Optional[str] = Query(None, description="Keyword search across filenames, labels, and scenes"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort direction (asc / desc)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve paginated image gallery records matching query filters."""
    service = ImageService(db)
    items, total = service.list_gallery(
        category=category,
        label=label,
        environment=environment,
        search=search,
        page=page,
        page_size=page_size,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "items": [img.to_dict() for img in items],
    }


@router.get(
    "/images/{image_id}",
    summary="Retrieve detailed image record with detections and DNA fingerprint",
)
def get_image_endpoint(image_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Fetch complete metadata, bounding boxes, dominant colors, and composition for an image."""
    service = ImageService(db)
    img = service.get_image(image_id)
    if not img:
        raise HTTPException(status_code=404, detail=f"Image #{image_id} not found.")

    res = img.to_dict()
    res["detections"] = [d.to_dict() for d in img.detections]
    res["dna"] = img.dna.to_dict() if img.dna else {}
    res["anomaly"] = img.anomaly.to_dict() if img.anomaly else None
    return res


@router.delete(
    "/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an image and its cascading detections and DNA records",
)
def delete_image_endpoint(image_id: int, db: Session = Depends(get_db)) -> None:
    """Delete image entity and remove cascading foreign key children."""
    success = delete_image(db, image_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Image #{image_id} not found.")


@router.post(
    "/search",
    summary="Natural language semantic image search",
)
def search_images_endpoint(
    payload: SearchRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Search images using natural language queries powered by CLIP text-to-image similarity."""
    service = SearchService(db)
    results = service.natural_language_search(query=payload.query, limit=payload.limit or 20)
    return {
        "query": payload.query,
        "total_results": len(results),
        "results": results,
    }


@router.post(
    "/ask",
    summary="Ask Your Images: Rule-based visual intelligence Q&A",
)
def ask_images_endpoint(
    payload: AskRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Query the image database using natural language questions without requiring an LLM."""
    service = SearchService(db)
    res = service.ask_images(payload.question)
    return {
        "question": res.question,
        "understood": res.understood,
        "intent": res.intent,
        "answer": res.answer,
        "total_found": res.total_found,
        "images": res.images,
        "suggestions": res.suggestions,
    }


@router.post(
    "/similar",
    summary="Reverse image search across multiple similarity modes",
)
async def similar_images_endpoint(
    file: UploadFile = File(...),
    mode: str = Form("overall", description="Mode: 'overall', 'object', 'color', or 'scene'"),
    limit: int = Form(12),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Find stored images visually or structurally similar to an uploaded query image."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty query image provided.")

    dna_service = DnaService(db)
    try:
        similar = dna_service.find_similar_by_image(
            image_bytes=content,
            mode=mode,
            limit=limit,
        )
        return {
            "mode": mode,
            "total_matches": len(similar),
            "matches": similar,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Similarity search failed: {exc}") from exc


@router.get(
    "/analytics",
    summary="Retrieve aggregated visual intelligence metrics for Chart.js",
)
def analytics_endpoint(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Compile database counts, top objects, category distributions, and monthly trends."""
    service = AnalyticsService(db)
    return service.get_dashboard_metrics()


@router.get(
    "/status",
    summary="Retrieve runtime database and model health diagnostic",
)
def status_endpoint() -> Dict[str, Any]:
    """Return runtime connection health and engine identity."""
    return {
        "database": get_db_status(),
        "models": {
            "object_detector": "YOLOv8n (Ultralytics)",
            "embedder": "CLIP ViT-B-32",
        },
    }
