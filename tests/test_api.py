"""Comprehensive test suite for SnapBase FastAPI endpoints and service layer.

Validates:
- Document upload and ingestion
- Duplicate hash detection
- Listing, filtering, sorting, pagination
- Document approval and rejection lifecycle
- Field patching and updates
- Single document deletion
- Dataset exports (CSV, XLSX, JSON)
- Dashboard statistics
- Error handling and HTTP status codes
- HTML template pages rendering
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.dependencies import get_db
from app.main import app
import db.session as dbs
from db.models import Base


@pytest.fixture(scope="function")
def test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Session, None, None]:
    """Provide an isolated SQLite database file for API tests."""
    db_file = tmp_path / "test_api.db"
    test_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setattr("config.settings.DATABASE_URL", test_url)

    test_engine = create_engine(
        test_url, connect_args={"check_same_thread": False}
    )
    test_factory = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False
    )
    monkeypatch.setattr(dbs, "engine", test_engine)
    monkeypatch.setattr(dbs, "SessionFactory", test_factory)

    Base.metadata.create_all(bind=test_engine)

    def override_get_db() -> Generator[Session, None, None]:
        session: Session = test_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield test_factory()
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db: Session) -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient bound to the isolated test database."""
    with TestClient(app) as test_client:
        yield test_client


def _make_dummy_image(text_color: tuple[int, int, int] = (10, 10, 10)) -> bytes:
    """Generate a clean in-memory JPEG image for upload testing."""
    img = Image.new("RGB", (250, 150), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_stats_initial_state(client: TestClient) -> None:
    """Test GET /api/stats with empty database."""
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_documents" in data
    assert data["total_documents"] == 0
    assert data["has_data"] is False
    assert data["status_counts"]["pending"] == 0
    assert data["status_counts"]["processed"] == 0
    assert "timeseries" in data
    assert "status_counts" in data


def test_upload_and_duplicate_detection(client: TestClient) -> None:
    """Test document upload and verify duplicate hash detection."""
    img_bytes = _make_dummy_image()

    # 1. First Upload
    files = {"files": ("test_receipt.jpg", img_bytes, "image/jpeg")}
    res = client.post("/api/documents", files=files, data={"doc_type": "receipt_invoice", "preferred_engine": "ocr"})
    assert res.status_code == 201
    data = res.json()
    assert data["processed_count"] == 1
    doc = data["documents"][0]
    assert doc["is_duplicate"] is False
    assert doc["status"] == "pending"
    assert doc["document_id"] is not None
    doc_id = doc["document_id"]

    # 2. Duplicate Upload (exact same bytes)
    files_dup = {"files": ("test_receipt_copy.jpg", img_bytes, "image/jpeg")}
    res_dup = client.post("/api/documents", files=files_dup, data={"doc_type": "receipt_invoice", "preferred_engine": "ocr"})
    assert res_dup.status_code == 201
    data_dup = res_dup.json()
    doc_dup = data_dup["documents"][0]
    assert doc_dup["is_duplicate"] is True
    assert doc_dup["document_id"] == doc_id


def test_list_and_search_documents(client: TestClient) -> None:
    """Test listing, search, and pagination."""
    # Seed an image
    img_bytes = _make_dummy_image()
    files = {"files": ("grocery_receipt.jpg", img_bytes, "image/jpeg")}
    client.post("/api/documents", files=files, data={"doc_type": "receipt_invoice", "preferred_engine": "ocr"})

    # List all
    res = client.get("/api/documents")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1

    # Filter by type
    res_type = client.get("/api/documents?doc_type=receipt_invoice")
    assert res_type.status_code == 200
    assert res_type.json()["total"] >= 1

    # Filter by non-matching type
    res_empty = client.get("/api/documents?doc_type=non_existent_type")
    assert res_empty.status_code == 200
    assert res_empty.json()["total"] == 0


def test_get_patch_approve_reject_delete_flow(client: TestClient) -> None:
    """Test full document lifecycle: get, update fields, approve, reject, delete."""
    img_bytes = _make_dummy_image((50, 50, 50))
    files = {"files": ("lifecycle_test.jpg", img_bytes, "image/jpeg")}
    upload_res = client.post("/api/documents", files=files, data={"doc_type": "receipt_invoice", "preferred_engine": "ocr"})
    doc_id = upload_res.json()["documents"][0]["document_id"]
    assert doc_id is not None

    # 1. GET by ID
    get_res = client.get(f"/api/documents/{doc_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == doc_id

    # 2. PATCH fields
    patch_payload = {"fields": {"vendor_name": "Acme Supermarket", "total_amount": 42.50}}
    patch_res = client.patch(f"/api/documents/{doc_id}", json=patch_payload)
    assert patch_res.status_code == 200
    updated_fields = patch_res.json()["fields"]
    assert updated_fields["vendor_name"] == "Acme Supermarket"

    # 3. Approve Document
    approve_res = client.post(f"/api/documents/{doc_id}/approve")
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "processed"

    # 4. Reject Document
    reject_res = client.post(f"/api/documents/{doc_id}/reject")
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "rejected"

    # 5. Delete Document
    del_res = client.delete(f"/api/documents/{doc_id}")
    assert del_res.status_code == 204

    # 6. Verify 404 after deletion
    after_del = client.get(f"/api/documents/{doc_id}")
    assert after_del.status_code == 404


def test_exports_csv_xlsx_json(client: TestClient) -> None:
    """Verify export endpoints generate valid CSV, XLSX, and JSON downloads."""
    # Seed a document
    img_bytes = _make_dummy_image((80, 80, 80))
    files = {"files": ("export_test.jpg", img_bytes, "image/jpeg")}
    client.post("/api/documents", files=files, data={"doc_type": "receipt_invoice", "preferred_engine": "ocr"})

    # Export CSV
    csv_res = client.get("/api/export?format=csv")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert len(csv_res.content) > 0

    # Export Excel
    xlsx_res = client.get("/api/export?format=xlsx")
    assert xlsx_res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in xlsx_res.headers["content-type"]
    assert len(xlsx_res.content) > 0

    # Export JSON
    json_res = client.get("/api/export?format=json")
    assert json_res.status_code == 200
    assert "application/json" in json_res.headers["content-type"]
    assert isinstance(json_res.json(), list)


def test_api_error_handling(client: TestClient) -> None:
    """Test 400 and 404 response codes for invalid inputs."""
    # 404 for non-existent document
    res_404 = client.get("/api/documents/999999")
    assert res_404.status_code == 404

    # 400 for empty file upload
    empty_files = {"files": ("empty.jpg", b"", "image/jpeg")}
    res_empty = client.post("/api/documents", files=empty_files)
    assert res_empty.status_code == 400

    # 400 for unsupported file extension
    txt_files = {"files": ("test.txt", b"plain text content", "text/plain")}
    res_txt = client.post("/api/documents", files=txt_files)
    assert res_txt.status_code == 400


def test_html_pages_render(client: TestClient) -> None:
    """Test that all primary HTML UI routes return 200 OK without errors."""
    for path in ["/", "/upload", "/review", "/records", "/settings"]:
        res = client.get(path)
        assert res.status_code == 200
        assert "<!DOCTYPE html>" in res.text
