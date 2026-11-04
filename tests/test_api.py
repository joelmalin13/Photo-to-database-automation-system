"""Comprehensive test suite for PixelMind FastAPI endpoints and web interface.
"""

from __future__ import annotations

import io
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_db
from app.main import app
from db.crud import create_image
from db.models import Base


@pytest.fixture(scope="function")
def test_client() -> Generator[TestClient, None, None]:
    """Provide TestClient backed by an isolated in-memory SQLite database using StaticPool."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_factory = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False
    )
    Base.metadata.create_all(bind=test_engine)

    # Pre-seed one image
    session = test_factory()
    create_image(
        session=session,
        filename="seed_test.jpg",
        stored_path="uploads/seed.jpg",
        annotated_path=None,
        sha256="seedhash1234567890abcdef",
        phash="1234567890abcdef",
        width=600,
        height=400,
        category="Vehicles",
        scene="street",
        environment="outdoor",
    )
    session.commit()
    session.close()

    def override_get_db() -> Generator[Session, None, None]:
        s = test_factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_html_pages_render(test_client: TestClient):
    """Verify all 8 HTML user interfaces render with HTTP 200 OK."""
    endpoints = [
        "/",
        "/upload",
        "/gallery",
        "/search",
        "/ask",
        "/similar",
        "/analytics",
        "/settings",
    ]
    for url in endpoints:
        resp = test_client.get(url)
        assert resp.status_code == 200, f"Failed for {url}: {resp.status_code}"
        assert "PixelMind" in resp.text or "PIXELMIND" in resp.text


def test_api_status(test_client: TestClient):
    """Verify /api/status endpoint returns database and model health."""
    resp = test_client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "database" in data
    assert "models" in data
    detector_name = data["models"]["object_detector"].lower()
    assert "yolov8" in detector_name or "gemini" in detector_name


def test_api_analytics(test_client: TestClient):
    """Verify /api/analytics returns chart-ready aggregations."""
    resp = test_client.get("/api/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_images" in data
    assert "category_dist" in data
    assert "scene_dist" in data


def test_api_list_images(test_client: TestClient):
    """Verify /api/images returns paginated JSON list."""
    resp = test_client.get("/api/images")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    assert data["items"][0]["filename"] == "seed_test.jpg"


def test_api_search_endpoint(test_client: TestClient):
    """Verify /api/search accepts natural language query and returns ranked results."""
    resp = test_client.post("/api/search", json={"query": "a car parked on the street"})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total_results" in data


def test_api_ask_endpoint(test_client: TestClient):
    """Verify /api/ask accepts question and returns rule-based answers."""
    resp = test_client.post("/api/ask", json={"question": "Find images containing dogs"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["understood"] is True
    assert "answer" in data


def test_api_upload_and_delete(test_client: TestClient):
    """Verify end-to-end image upload and subsequent deletion."""
    # Create unique in-memory 100x100 RGB image
    img = PILImage.new("RGB", (100, 100), color=(123, 210, 85))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    upload_resp = test_client.post(
        "/api/images",
        files=[("files", ("unit_test_upload.jpg", image_bytes, "image/jpeg"))],
        data={"confidence_threshold": "0.25"},
    )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    assert upload_data["success"] is True
    assert upload_data["processed_count"] == 1
    created_id = upload_data["images"][0]["id"]

    # Verify detail retrieval
    detail_resp = test_client.get(f"/api/images/{created_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["id"] == created_id
    assert "dna" in detail_data

    # Verify deletion
    del_resp = test_client.delete(f"/api/images/{created_id}")
    assert del_resp.status_code == 204

    # Verify 404 after deletion
    after_del = test_client.get(f"/api/images/{created_id}")
    assert after_del.status_code == 404
