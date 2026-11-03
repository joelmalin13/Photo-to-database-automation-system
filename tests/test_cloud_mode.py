"""Cloud-mode deployment tests for PixelMind on Vercel.

Validates that:
1. Zero heavy deep-learning packages (torch, torchvision, ultralytics, cv2, scipy, open_clip)
   are imported when running in Cloud Mode.
2. Google Gemini Vision detection works end-to-end with structured JSON output and Pillow rendering.
3. Embeddings are stored as portable JSON lists of floats, not binary blobs.
4. Natural language search and Ask Your Images work cleanly in cloud mode.
5. GET /health reports accurate system telemetry without leaking secrets.
"""

from __future__ import annotations

import io
import json
import os
import sys
from typing import Any, Generator
from unittest.mock import MagicMock, patch
import numpy as np
from PIL import Image as PILImage
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# -------------------------------------------------------------
# Test 1: Module Isolation (Zero Torch / OpenCV in Cloud Mode)
# -------------------------------------------------------------

def test_cloud_mode_zero_torch_or_cv2() -> None:
    """Ensure cloud mode can be imported and initialized without torch, ultralytics, or cv2."""
    forbidden = ["torch", "torchvision", "ultralytics", "open_clip", "cv2", "scipy"]
    
    # Save original modules
    original_modules = {}
    for mod in forbidden:
        if mod in sys.modules:
            original_modules[mod] = sys.modules.pop(mod)

    # Inject dummy None to block importing
    for mod in forbidden:
        sys.modules[mod] = None  # Causes ImportError if attempted to import

    try:
        # Set cloud mode in environment
        os.environ["AI_MODE"] = "cloud"
        os.environ["VERCEL"] = "1"

        # Import core modules
        import index
        from app.main import app
        from core.cloud_detector import CloudDetector, GeminiVisionSchema
        from core.dna import extract_dominant_colors, compute_phash, compute_sha256
        from core.embedder import CloudEmbedder, get_embedder
        from core.storage import LocalStorage, SupabaseStorage, get_storage

        # Verify pure Pillow/NumPy dominant color extraction works without cv2
        img = PILImage.new("RGB", (100, 100), color=(255, 0, 0))
        colors = extract_dominant_colors(img, num_colors=3)
        assert len(colors) > 0
        assert colors[0]["hex"] == "#FF0000"

        # Verify perceptual hash works without scipy or cv2
        ph = compute_phash(img)
        assert isinstance(ph, str) and len(ph) == 16

        # Verify CloudEmbedder initializes without torch
        embedder = CloudEmbedder()
        vec = embedder.embed_text("test query")
        assert isinstance(vec, list)
        assert len(vec) in (512, 768)
        assert all(isinstance(x, float) for x in vec)

    finally:
        # Restore sys.modules
        for mod in forbidden:
            sys.modules.pop(mod, None)
            if mod in original_modules:
                sys.modules[mod] = original_modules[mod]


# -------------------------------------------------------------
# Fixtures for In-Memory SQLite Cloud Testing
# -------------------------------------------------------------

@pytest.fixture
def cloud_db() -> Generator[Session, None, None]:
    """Provide isolated in-memory SQLite session with initialized schema."""
    from db.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_gemini_vision() -> GeminiVisionSchema:
    """Mock structured Gemini vision response."""
    from core.cloud_detector import DetectedObjectSchema, GeminiVisionSchema

    return GeminiVisionSchema(
        objects=[
            DetectedObjectSchema(
                label="car",
                count=2,
                confidence=0.96,
                box_2d=[0.2, 0.1, 0.7, 0.8],
            ),
            DetectedObjectSchema(
                label="tree",
                count=3,
                confidence=0.88,
                box_2d=[0.05, 0.6, 0.9, 0.95],
            ),
        ],
        caption="Two red cars parked along a tree-lined street.",
        scene="street",
        environment="outdoor",
        context="Urban roadway under daytime conditions",
        category="Vehicles",
    )


# -------------------------------------------------------------
# Test 2: Cloud Ingestion Pipeline with Mock Gemini
# -------------------------------------------------------------

def test_cloud_ingestion_end_to_end(
    cloud_db: Session,
    mock_gemini_vision: Any,
) -> None:
    """Test full ingestion pipeline using CloudDetector and CloudEmbedder."""
    os.environ["AI_MODE"] = "cloud"
    from app.services.image_service import ImageService
    from core.cloud_detector import CloudDetector

    # Create dummy image bytes
    img = PILImage.new("RGB", (400, 300), color=(200, 50, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    with patch.object(CloudDetector, "_call_gemini_vision", return_value=mock_gemini_vision):
        service = ImageService(cloud_db)
        image_entity, is_dup, msg = service.ingest_image(
            filename="street_scene.jpg",
            file_bytes=img_bytes,
        )

        assert not is_dup
        assert image_entity.status == "done"
        assert image_entity.category == "Vehicles"
        assert image_entity.scene == "street"
        assert image_entity.environment == "outdoor"
        assert "Two red cars" in (image_entity.caption or "")

        # Verify detections
        assert len(image_entity.detections) == 2
        labels = {d.label for d in image_entity.detections}
        assert "car" in labels
        assert "tree" in labels

        # Verify DNA with JSON embedding
        assert image_entity.dna is not None
        assert image_entity.dna.embedding_json is not None
        assert isinstance(image_entity.dna.embedding_json, list)
        assert len(image_entity.dna.embedding_json) in (512, 768)
        assert len(image_entity.dna.dominant_colors_json) > 0


# -------------------------------------------------------------
# Test 3: Cloud Search & Q&A
# -------------------------------------------------------------

def test_cloud_search_and_ask(
    cloud_db: Session,
    mock_gemini_vision: Any,
) -> None:
    """Verify semantic search and Ask Your Images work over cloud-ingested data."""
    os.environ["AI_MODE"] = "cloud"
    from app.services.image_service import ImageService
    from app.services.search_service import SearchService
    from core.cloud_detector import CloudDetector

    img = PILImage.new("RGB", (400, 300), color=(50, 150, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    with patch.object(CloudDetector, "_call_gemini_vision", return_value=mock_gemini_vision):
        service = ImageService(cloud_db)
        service.ingest_image(filename="parked_cars.jpg", file_bytes=img_bytes)

    # 1. Natural Language Search
    search_service = SearchService(cloud_db)
    results = search_service.natural_language_search("a red car parked by a tree")
    assert len(results) > 0
    assert results[0]["filename"] == "parked_cars.jpg"
    assert "similarity_score" in results[0]

    # 2. Ask Your Images Rule-based Q&A
    qa_res = search_service.ask_images("How many cars have been detected across all images?")
    assert qa_res.understood
    assert "2" in qa_res.answer or "car" in qa_res.answer.lower()
    assert len(qa_res.images) > 0


# -------------------------------------------------------------
# Test 4: Health Check Telemetry in Cloud Mode
# -------------------------------------------------------------

def test_cloud_health_endpoint() -> None:
    """Verify GET /health returns cloud configuration without exposing secrets."""
    from app.main import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] in ("healthy", "degraded")
    assert "database" in data
    assert "storage" in data
    assert "ai" in data
    assert "detector" in data["ai"]

    # Security: No secret tokens in telemetry
    dumped = json.dumps(data)
    assert "AIza" not in dumped  # Google API key prefix
    assert "eyJ" not in dumped   # JWT prefix
