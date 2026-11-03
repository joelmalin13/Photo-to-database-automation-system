"""HTML Page routing and Jinja2 server-rendered views for PixelMind.

Renders responsive views styled with Tailwind CSS, Alpine.js, and HTMX.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.analytics_service import AnalyticsService
from app.services.dna_service import DnaService
from app.services.image_service import ImageService
from app.services.search_service import SearchService
from config.settings import BASE_DIR, load_categories_config, load_scenes_config
from db.crud import get_image_by_id
from db.session import get_db_status

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def _base_context(request: Request, active_page: str) -> Dict[str, Any]:
    """Compile common context variables for layout navigation."""
    return {
        "request": request,
        "active_page": active_page,
        "db_status": get_db_status(),
        "app_name": "PIXELMIND",
        "tagline": "Every Image Has Data. Make It Searchable.",
    }


@router.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Render home analytics and KPI summary dashboard."""
    ctx = _base_context(request, "dashboard")
    analytics = AnalyticsService(db).get_dashboard_metrics()
    ctx["analytics"] = analytics

    # Recent images
    images, _ = ImageService(db).list_gallery(page=1, page_size=6)
    ctx["recent_images"] = images
    return templates.TemplateResponse(request=request, name="dashboard.html", context=ctx)


@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request) -> HTMLResponse:
    """Render multi-file upload portal."""
    ctx = _base_context(request, "upload")
    return templates.TemplateResponse(request=request, name="upload.html", context=ctx)


@router.get("/gallery", response_class=HTMLResponse)
def gallery_page(
    request: Request,
    category: Optional[str] = Query(None),
    label: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render visual gallery with filtering, sorting, and pagination."""
    ctx = _base_context(request, "gallery")
    service = ImageService(db)
    items, total = service.list_gallery(
        category=category,
        label=label,
        environment=environment,
        search=search,
        page=page,
        page_size=12,
    )
    ctx["items"] = items
    ctx["total"] = total
    ctx["page"] = page
    ctx["total_pages"] = max(1, (total + 11) // 12)
    ctx["category_filter"] = category or "all"
    ctx["env_filter"] = environment or "all"
    ctx["search_query"] = search or ""
    ctx["categories"] = load_scenes_config().get("canonical_categories", [])
    return templates.TemplateResponse(request=request, name="gallery.html", context=ctx)


@router.get("/partials/gallery-grid", response_class=HTMLResponse)
def gallery_grid_partial(
    request: Request,
    category: Optional[str] = Query(None),
    label: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """HTMX partial rendering filtered image cards and pagination."""
    service = ImageService(db)
    items, total = service.list_gallery(
        category=category,
        label=label,
        environment=environment,
        search=search,
        page=page,
        page_size=12,
    )
    ctx = {
        "request": request,
        "items": items,
        "total": total,
        "page": page,
        "total_pages": max(1, (total + 11) // 12),
        "category_filter": category or "all",
        "env_filter": environment or "all",
    }
    return templates.TemplateResponse(request=request, name="partials/gallery_grid.html", context=ctx)


@router.get("/images/{image_id}", response_class=HTMLResponse)
def image_detail_page(image_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Render comprehensive image detail view with DNA card and detections."""
    img = get_image_by_id(db, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image record not found.")

    ctx = _base_context(request, "gallery")
    ctx["image"] = img
    # Similar images
    similar = DnaService(db).find_similar_to_stored(image_id, mode="overall", limit=4)
    ctx["similar_images"] = similar
    return templates.TemplateResponse(request=request, name="image_detail.html", context=ctx)


@router.get("/search", response_class=HTMLResponse)
def search_page(request: Request, q: Optional[str] = Query(None), db: Session = Depends(get_db)) -> HTMLResponse:
    """Render natural language search portal."""
    ctx = _base_context(request, "search")
    ctx["query"] = q or ""
    results = []
    if q and q.strip():
        results = SearchService(db).natural_language_search(q.strip(), limit=20)
    ctx["results"] = results
    return templates.TemplateResponse(request=request, name="search.html", context=ctx)


@router.get("/partials/search-results", response_class=HTMLResponse)
def search_results_partial(request: Request, q: str = Query(""), db: Session = Depends(get_db)) -> HTMLResponse:
    """HTMX partial for debounced live search results."""
    results = []
    if q and q.strip():
        results = SearchService(db).natural_language_search(q.strip(), limit=20)
    ctx = {"request": request, "results": results, "query": q}
    return templates.TemplateResponse(request=request, name="partials/search_results.html", context=ctx)


@router.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request) -> HTMLResponse:
    """Render Ask Your Images conversational interface."""
    ctx = _base_context(request, "ask")
    return templates.TemplateResponse(request=request, name="ask.html", context=ctx)


@router.post("/partials/ask-response", response_class=HTMLResponse)
def ask_response_partial(request: Request, question: str = Form(...), db: Session = Depends(get_db)) -> HTMLResponse:
    """HTMX partial for Ask Your Images query answer."""
    res = SearchService(db).ask_images(question)
    ctx = {"request": request, "result": res}
    return templates.TemplateResponse(request=request, name="partials/ask_response.html", context=ctx)


@router.get("/similar", response_class=HTMLResponse)
def similar_page(request: Request) -> HTMLResponse:
    """Render reverse image intelligence portal."""
    ctx = _base_context(request, "similar")
    return templates.TemplateResponse(request=request, name="similar.html", context=ctx)


@router.post("/partials/similar-results", response_class=HTMLResponse)
async def similar_results_partial(
    request: Request,
    file: UploadFile = Form(...),
    mode: str = Form("overall"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """HTMX partial displaying reverse image matches."""
    content = await file.read()
    matches = []
    error = None
    if content:
        try:
            matches = DnaService(db).find_similar_by_image(content, mode=mode, limit=12)
        except Exception as exc:
            error = str(exc)

    ctx = {"request": request, "matches": matches, "mode": mode, "error": error}
    return templates.TemplateResponse(request=request, name="partials/similar_results.html", context=ctx)


@router.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Render deep analytics and Chart.js visualizations."""
    ctx = _base_context(request, "analytics")
    ctx["analytics"] = AnalyticsService(db).get_dashboard_metrics()
    return templates.TemplateResponse(request=request, name="analytics.html", context=ctx)


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request) -> HTMLResponse:
    """Render settings and diagnostic telemetry."""
    ctx = _base_context(request, "settings")
    return templates.TemplateResponse(request=request, name="settings.html", context=ctx)
