"""Unit tests for PixelMind database models and CRUD operations.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.crud import (
    add_detections,
    create_image,
    delete_image,
    find_image_by_hash,
    flag_anomaly,
    get_analytics_summary,
    get_image_by_id,
    list_images,
    set_image_dna,
)
from db.models import Anomaly, Base, Detection, Image, ImageDNA


@pytest.fixture
def db_session() -> Session:
    """Provide isolated in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_create_and_find_image(db_session: Session):
    """Verify image creation, persistence, and SHA-256 hash lookup."""
    sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    img = create_image(
        session=db_session,
        filename="test_photo.jpg",
        stored_path="uploads/test_photo.jpg",
        annotated_path="annotated/test_photo.jpg",
        sha256=sha,
        phash="0123456789abcdef",
        width=1920,
        height=1080,
        category="Vehicles",
        scene="street",
        environment="outdoor",
    )
    db_session.commit()

    assert img.id is not None
    assert img.filename == "test_photo.jpg"

    # Lookup by hash
    found = find_image_by_hash(db_session, sha)
    assert found is not None
    assert found.id == img.id


def test_add_detections_and_dna(db_session: Session):
    """Verify detection insertion and Image DNA persistence."""
    img = create_image(
        session=db_session,
        filename="office.jpg",
        stored_path="uploads/office.jpg",
        annotated_path=None,
        sha256="abc123456789",
        phash=None,
        width=1280,
        height=720,
        category="Electronics",
    )
    db_session.commit()

    # Add detections
    dets = [
        {"label": "laptop", "category": "Electronics", "count": 2, "avg_confidence": 0.92, "bboxes": []},
        {"label": "chair", "category": "Architecture", "count": 4, "avg_confidence": 0.81, "bboxes": []},
    ]
    records = add_detections(db_session, img.id, dets)
    assert len(records) == 2

    # Set DNA
    colors = [{"hex": "#FFFFFF", "rgb": [255, 255, 255], "percentage": 70.0}]
    comp = {"aspect_ratio": 1.78, "total_objects": 6}
    dna = set_image_dna(db_session, img.id, colors, None, comp)
    assert dna.image_id == img.id
    assert len(dna.dominant_colors_json) == 1
    db_session.commit()
    db_session.expire_all()

    # Verify relationships
    refetched = get_image_by_id(db_session, img.id)
    assert len(refetched.detections) == 2
    assert refetched.dna is not None


def test_flag_anomaly(db_session: Session):
    """Verify anomaly flagging on an image."""
    img = create_image(
        session=db_session,
        filename="weird.jpg",
        stored_path="uploads/weird.jpg",
        annotated_path=None,
        sha256="weirdhash123",
        phash=None,
        width=800,
        height=600,
        category="Animals",
    )
    db_session.commit()

    anom = flag_anomaly(db_session, img.id, "Abnormal object density: 35 objects", 3.2)
    db_session.commit()

    assert anom.image_id == img.id
    refetched = get_image_by_id(db_session, img.id)
    assert refetched.anomaly is not None
    assert refetched.anomaly.score == 3.2


def test_delete_image_cascade(db_session: Session):
    """Verify deleting an image cascades to detections, DNA, and anomaly."""
    img = create_image(
        session=db_session,
        filename="delete_me.jpg",
        stored_path="uploads/delete_me.jpg",
        annotated_path=None,
        sha256="delhash",
        phash=None,
        width=800,
        height=600,
    )
    db_session.commit()
    add_detections(db_session, img.id, [{"label": "cat", "category": "Animals", "count": 1}])
    set_image_dna(db_session, img.id, [], None, {})
    flag_anomaly(db_session, img.id, "Test anomaly", 1.5)
    db_session.commit()

    assert delete_image(db_session, img.id) is True
    db_session.commit()

    assert get_image_by_id(db_session, img.id) is None
    assert db_session.get(Detection, 1) is None
    assert db_session.get(ImageDNA, img.id) is None
    assert db_session.get(Anomaly, img.id) is None


def test_list_and_filter_images(db_session: Session):
    """Verify category filtering and pagination."""
    for i in range(15):
        cat = "Vehicles" if i % 2 == 0 else "Animals"
        create_image(
            session=db_session,
            filename=f"img_{i}.jpg",
            stored_path=f"uploads/img_{i}.jpg",
            annotated_path=None,
            sha256=f"hash_{i}",
            phash=None,
            width=800,
            height=600,
            category=cat,
            environment="outdoor" if i % 2 == 0 else "indoor",
        )
    db_session.commit()

    # Total 15
    items, total = list_images(db_session, page=1, page_size=10)
    assert total == 15
    assert len(items) == 10

    # Filter Vehicles
    items_v, total_v = list_images(db_session, category="Vehicles")
    assert total_v == 8
    assert all(x.category == "Vehicles" for x in items_v)


def test_get_analytics_summary(db_session: Session):
    """Verify aggregated metrics for charts."""
    summary = get_analytics_summary(db_session)
    assert "total_images" in summary
    assert "top_objects" in summary
    assert "category_dist" in summary
    assert "scene_dist" in summary

