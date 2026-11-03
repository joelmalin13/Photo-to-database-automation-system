"""REST API endpoints for SnapBase document processing and queries.

Exposes structured JSON endpoints for uploading, querying, approving,
rejecting, modifying, and exporting document records.
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
from app.services.export_service import ExportService
from app.services.stats_service import StatsService

api_router = APIRouter(prefix="/api", tags=["Documents & Analytics"])


class DocumentFieldUpdate(BaseModel):
    """Payload schema for updating extracted document attributes."""

    fields: Dict[str, Any] = Field(
        ..., description="Key-value dictionary of updated fields"
    )


@api_router.post(
    "/documents",
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process document images",
)
async def upload_documents(
    files: List[UploadFile] = File(...),
    doc_type: str = Form("auto"),
    preferred_engine: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Ingest, validate, preprocess, and extract structured data from images."""
    service = DocumentService(db)
    results = []
    for file in files:
        res = await service.ingest_upload(
            file, doc_type=doc_type, preferred_engine=preferred_engine
        )
        results.append(
            {
                "filename": res.filename,
                "document_id": res.document_id,
                "type": res.doc_type,
                "status": res.status,
                "is_duplicate": res.is_duplicate,
                "engine_used": res.engine_used,
                "fields": res.fields,
                "confidences": res.confidences,
                "warnings": res.warnings,
                "error": res.error_message,
            }
        )
    return {"processed_count": len(results), "documents": results}


@api_router.get(
    "/documents",
    summary="List, search, filter, and paginate documents",
)
def list_documents_endpoint(
    doc_type: Optional[str] = Query(None),
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
    items, total = service.list_documents(
        doc_type=doc_type,
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


@api_router.patch(
    "/documents/{doc_id}", summary="Update document extracted fields"
)
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


@api_router.post(
    "/documents/{doc_id}/approve", summary="Approve document record"
)
def approve_document_endpoint(
    doc_id: int, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Transition document status to approved/processed."""
    service = DocumentService(db)
    doc = service.approve_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    return doc


@api_router.post("/documents/{doc_id}/reject", summary="Reject document record")
def reject_document_endpoint(
    doc_id: int, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Transition document status to rejected."""
    service = DocumentService(db)
    doc = service.reject_document(doc_id)
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


@api_router.get("/stats", summary="Get dashboard performance metrics")
def get_stats_endpoint(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve operational KPIs, category ratios, and time-series history."""
    service = StatsService(db)
    return service.get_dashboard_data()


@api_router.get("/export", summary="Export document dataset")
def export_dataset_endpoint(
    format: str = Query("csv", pattern="^(csv|xlsx|json)$"),
    doc_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    """Stream exported CSV, Excel, or JSON datasets."""
    service = ExportService(db)
    payload, media_type, filename = service.export(
        export_format=format,
        doc_type=doc_type,
        status=status,
        search_query=search,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type=media_type, headers=headers)
