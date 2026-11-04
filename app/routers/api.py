"""REST API endpoints for SnapBase document processing, computer vision, and reporting.

Exposes structured JSON endpoints for:
- Single & batch document ingestion
- Interactive image enhancement playground
- Human-in-the-loop verification & confirmed table promotion
- Multi-criteria database querying
- Operational analytics and report generation
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.document_service import DocumentService
from app.services.image_processing_service import ImageProcessingService
from app.services.ask_receipts_service import AskReceiptsService
from app.services.report_service import ReportService
from app.services.stats_service import StatsService

api_router = APIRouter(prefix="/api", tags=["SnapBase API"])


class DocumentFieldUpdate(BaseModel):
    """Payload schema for modifying extracted document fields."""
    fields: Dict[str, Any] = Field(..., description="Key-value dictionary of updated fields")
    items: Optional[List[Dict[str, Any]]] = Field(default=None, description="Line items or mark rows")


class ApprovePayload(BaseModel):
    """Optional payload when explicitly approving verified fields."""
    fields: Optional[Dict[str, Any]] = None
    items: Optional[List[Dict[str, Any]]] = None


@api_router.post(
    "/documents",
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest document photographs",
)
async def upload_documents(
    files: List[UploadFile] = File(...),
    doc_type: str = Form("auto"),
    preferred_engine: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Ingest, validate, preprocess, and extract structured data from one or more images."""
    service = DocumentService(db)
    results = []
    for file in files:
        res = await service.ingest_upload(
            file, category=doc_type, preferred_engine=preferred_engine
        )
        results.append(
            {
                "filename": res.filename,
                "document_id": res.document_id,
                "category": res.doc_type,
                "type": res.doc_type,
                "status": res.status,
                "is_duplicate": res.is_duplicate,
                "engine_used": res.engine_used,
                "fields": res.fields,
                "confidences": res.confidences,
                "warnings": res.warnings,
                "error": res.error_message,
                "word_confidences": res.word_confidences,
            }
        )
    return {"processed_count": len(results), "documents": results}


@api_router.get("/documents", summary="List, search, filter, and paginate documents")
def list_documents_endpoint(
    doc_type: Optional[str] = Query(None, alias="category"),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve paginated collection of documents based on query filters."""
    service = DocumentService(db)
    cat_filter = category or doc_type
    items, total = service.list_documents(
        category=cat_filter,
        status=status,
        search_query=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@api_router.get("/documents/{doc_id}", summary="Get document by ID")
def get_document_endpoint(
    doc_id: int, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Fetch single document record by primary key."""
    service = DocumentService(db)
    doc = service.get_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    return doc


@api_router.patch("/documents/{doc_id}", summary="Update document extracted fields")
def update_document_fields_endpoint(
    doc_id: int,
    payload: DocumentFieldUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Modify extracted fields for an existing document."""
    service = DocumentService(db)
    doc = service.update_fields(doc_id, payload.fields)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    return doc


@api_router.post("/documents/{doc_id}/approve", summary="Approve and promote to confirmed table")
def approve_document_endpoint(
    doc_id: int,
    payload: Optional[ApprovePayload] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Approve document and promote data into official normalized confirmed tables (receipts/students/cards)."""
    service = DocumentService(db)
    fields = payload.fields if payload else None
    items = payload.items if payload else None
    doc = service.approve_document(doc_id, verified_fields=fields, items=items)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    return doc


@api_router.post("/documents/{doc_id}/reject", summary="Reject document record")
def reject_document_endpoint(
    doc_id: int,
    reason: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Transition document status to rejected."""
    service = DocumentService(db)
    doc = service.reject_document(doc_id, reason=reason)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    return doc


@api_router.delete(
    "/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document record",
)
def delete_document_endpoint(
    doc_id: int, db: Session = Depends(get_db)
) -> Response:
    """Delete document entity and associated disk file."""
    service = DocumentService(db)
    deleted = service.delete_document(doc_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.post("/image-processing/preview", summary="Interactive image enhancement and OCR retry")
async def image_processing_preview(
    file: UploadFile = File(...),
    rotate_deg: float = Form(0.0),
    grayscale: bool = Form(True),
    denoise: bool = Form(True),
    gaussian_blur: bool = Form(False),
    sharpen: bool = Form(False),
    threshold_method: str = Form("none"),
    clahe: bool = Form(True),
    perspective: bool = Form(False),
    run_ocr: bool = Form(False),
    engine: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Apply modular computer vision enhancements and optionally run OCR."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    result = ImageProcessingService.process_and_preview(
        image_bytes=content,
        rotate_deg=rotate_deg,
        grayscale=grayscale,
        denoise=denoise,
        gaussian_blur=gaussian_blur,
        sharpen=sharpen,
        threshold_method=threshold_method,
        clahe=clahe,
        perspective=perspective,
        run_ocr=run_ocr,
        engine_name=engine,
    )
    return result


@api_router.get("/stats", summary="Get dashboard performance metrics")
def get_stats_endpoint(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve operational KPIs, category ratios, and time-series history."""
    service = StatsService(db)
    return service.get_dashboard_data()


@api_router.get("/analytics", summary="Get complete analytics data for Chart.js")
def get_analytics_endpoint(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve category distribution, expense trends, and performance breakdowns."""
    service = StatsService(db)
    return service.get_full_analytics()


@api_router.get("/export", summary="Export document dataset or generate summary report")
def export_dataset_endpoint(
    format: str = Query("xlsx", pattern="^(xlsx|csv|json|summary)$"),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    """Stream formatted Excel, CSV, JSON, or text summary report."""
    service = ReportService(db)
    payload, media_type, filename = service.generate_report(
        export_format=format,
        category=category,
        status=status,
        search_query=search,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type=media_type, headers=headers)


class AskReceiptsPayload(BaseModel):
    question: str


@api_router.post("/ask-receipts", summary="Ask natural language questions about saved receipts (Slide 6 #6)")
def ask_receipts_endpoint(
    payload: AskReceiptsPayload,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Answer natural language query about spending, shops, categories, and totals."""
    service = AskReceiptsService(db)
    return service.query(payload.question)


@api_router.get("/demo/abc-mart", summary="Download or preview the ABC MART demo receipt (Slide 7)")
def get_demo_receipt() -> Response:
    from config.settings import BASE_DIR
    demo_path = BASE_DIR / "sample_data" / "abc_mart_receipt.png"
    if not demo_path.exists():
        raise HTTPException(status_code=404, detail="Demo receipt not found")
    with open(demo_path, "rb") as f:
        data = f.read()
    return Response(content=data, media_type="image/png")
