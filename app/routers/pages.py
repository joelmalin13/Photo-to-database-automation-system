"""HTML page and HTMX partial routes for SnapBase application.

Renders Jinja2 templates for:
- Home Dashboard (/)
- Upload Documents (/upload)
- Image Processing (/image-processing)
- Extracted Information & Review (/review, /review/{doc_id})
- Database Records (/records)
- Analytics (/analytics)
- Export Reports (/reports)
- Settings (/settings)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.document_service import DocumentService
from app.services.stats_service import StatsService
from config.settings import (
    BASE_DIR,
    CONFIDENCE_THRESHOLD,
    DEFAULT_ENGINE,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    THEME_PRIMARY,
    load_schemas,
)
from db.session import get_db_status

pages_router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def _base_context(request: Request, active_page: str, title: str) -> Dict[str, Any]:
    """Construct shared navigation, database health, and engine context."""
    db_stat = get_db_status()
    return {
        "request": request,
        "active_page": active_page,
        "page_title": title,
        "db_status": db_stat,
        "db_engine": db_stat.get("engine_name", "SQLite"),
        "db_is_fallback": db_stat.get("is_fallback", False),
        "gemini_active": bool(GEMINI_API_KEY),
        "engine_name": DEFAULT_ENGINE.upper(),
        "model_name": GEMINI_MODEL,
        "primary_color": THEME_PRIMARY,
    }


@pages_router.get("/", response_class=HTMLResponse)
def dashboard_page(
    request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    """Render central analytics and KPI dashboard."""
    stats = StatsService(db).get_dashboard_data()
    ctx = _base_context(request, "dashboard", "Dashboard")
    ctx["stats"] = stats
    return templates.TemplateResponse(request=request, name="dashboard.html", context=ctx)


@pages_router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request) -> HTMLResponse:
    """Render drag-and-drop document upload and camera capture interface."""
    schemas = load_schemas()
    ctx = _base_context(request, "upload", "Upload Documents")
    ctx["schemas"] = schemas
    return templates.TemplateResponse(request=request, name="upload.html", context=ctx)


@pages_router.get("/image-processing", response_class=HTMLResponse)
def image_processing_page(request: Request) -> HTMLResponse:
    """Render interactive computer vision enhancement playground."""
    ctx = _base_context(request, "image_processing", "Image Processing Playground")
    return templates.TemplateResponse(request=request, name="image_processing.html", context=ctx)


@pages_router.get("/review", response_class=HTMLResponse)
def review_default_page(
    request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    """Render verification editor for first pending document or empty state."""
    service = DocumentService(db)
    docs, _ = service.list_documents(status="processed", page=1, page_size=1)
    if docs:
        return review_document_page(docs[0]["id"], request, db)
    # Check any document if none are unverified
    all_docs, _ = service.list_documents(page=1, page_size=1)
    if all_docs:
        return review_document_page(all_docs[0]["id"], request, db)

    ctx = _base_context(request, "review", "Extracted Information Review")
    ctx["document"] = None
    return templates.TemplateResponse(request=request, name="review.html", context=ctx)


@pages_router.get("/review/{doc_id}", response_class=HTMLResponse)
def review_document_page(
    doc_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    """Render split-screen verification interface for a specific document."""
    service = DocumentService(db)
    doc = service.get_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )

    all_docs, _ = service.list_documents(page=1, page_size=100)
    schemas = load_schemas()
    category_key = doc.get("category", "receipts")
    if category_key == "receipt_invoice":
        category_key = "receipts"
    elif category_key in ("student_marksheet", "student_id_form"):
        category_key = "students"
    elif category_key == "business_card":
        category_key = "business_cards"

    schema_def = schemas.get(category_key, schemas.get("receipts", {}))

    ctx = _base_context(request, "review", f"Review #{doc_id}")
    ctx.update(
        {
            "document": doc,
            "all_docs": all_docs,
            "schema_fields": schema_def.get("fields", []),
            "confidence_threshold": CONFIDENCE_THRESHOLD,
        }
    )
    return templates.TemplateResponse(request=request, name="review.html", context=ctx)


@pages_router.get("/records", response_class=HTMLResponse)
def records_page(
    request: Request,
    category: Optional[str] = Query(None, alias="doc_type"),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render confirmed database records repository with live search and filtering."""
    service = DocumentService(db)
    items, total = service.list_documents(
        category=category,
        status=status_filter,
        search_query=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=10,
    )
    ctx = _base_context(request, "records", "Database Records")
    ctx.update(
        {
            "items": items,
            "total": total,
            "page": page,
            "total_pages": max(1, (total + 9) // 10),
            "schemas": load_schemas(),
            "current_type": category or "all",
            "current_status": status_filter or "all",
            "search_query": search or "",
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
    )
    return templates.TemplateResponse(request=request, name="records.html", context=ctx)


@pages_router.get("/analytics", response_class=HTMLResponse)
def analytics_page(
    request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    """Render dedicated analytics dashboards with Chart.js charts."""
    analytics = StatsService(db).get_full_analytics()
    ctx = _base_context(request, "analytics", "Operational Analytics")
    ctx["analytics"] = analytics
    return templates.TemplateResponse(request=request, name="analytics.html", context=ctx)


@pages_router.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    """Render formatted export reports and executive summary downloads."""
    stats = StatsService(db).get_dashboard_data()
    ctx = _base_context(request, "reports", "Export Reports")
    ctx["stats"] = stats
    ctx["schemas"] = load_schemas()
    return templates.TemplateResponse(request=request, name="reports.html", context=ctx)


@pages_router.get("/partials/records-table", response_class=HTMLResponse)
def partial_records_table(
    request: Request,
    category: Optional[str] = Query(None, alias="doc_type"),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Return HTMX partial snippet for records table."""
    service = DocumentService(db)
    items, total = service.list_documents(
        category=category,
        status=status_filter,
        search_query=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=10,
    )
    ctx = {
        "request": request,
        "items": items,
        "total": total,
        "page": page,
        "total_pages": max(1, (total + 9) // 10),
        "current_type": category or "all",
        "current_status": status_filter or "all",
        "search_query": search or "",
    }
    return templates.TemplateResponse(
        request=request, name="partials/records_table.html", context=ctx
    )


@pages_router.get("/partials/drawer/{doc_id}", response_class=HTMLResponse)
def partial_detail_drawer(
    doc_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    """Return HTMX partial snippet for slide drawer inspection."""
    service = DocumentService(db)
    doc = service.get_document(doc_id)
    if not doc:
        return HTMLResponse("<div class='p-4 text-red-600'>Document not found</div>")
    ctx = {"request": request, "document": doc}
    return templates.TemplateResponse(
        request=request, name="partials/drawer.html", context=ctx
    )


@pages_router.get("/file/image/{doc_id}")
def serve_document_image(
    doc_id: int, db: Session = Depends(get_db)
) -> FileResponse:
    """Serve preprocessed image from filesystem."""
    service = DocumentService(db)
    doc = service.get_document(doc_id)
    if not doc or not Path(doc["image_path"]).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image file not found."
        )
    return FileResponse(doc["image_path"])


@pages_router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request) -> HTMLResponse:
    """Render system settings and live MySQL/SQLite connection diagnostic view."""
    ctx = _base_context(request, "settings", "Settings")
    ctx.update(
        {
            "engine": DEFAULT_ENGINE,
            "model": GEMINI_MODEL,
            "threshold": int(CONFIDENCE_THRESHOLD * 100),
            "theme_accent": THEME_PRIMARY,
        }
    )
    return templates.TemplateResponse(request=request, name="settings.html", context=ctx)
