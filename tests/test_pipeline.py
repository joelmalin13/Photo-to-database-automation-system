"""Integration and unit tests for the SnapBase processing pipeline.

Tests image validation, hash computing, blur detection, offline extraction,
duplicate detection, and generator batch processing.
"""

from __future__ import annotations

import io
from pathlib import Path
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import DocumentStatus
from core.exceptions import ValidationError
from core.pipeline import batch_process_images, process_single_image
from core.preprocess import (
    compute_image_hash,
    validate_image_bytes,
)
import db.session as dbs
from db.models import Base


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide an isolated SQLite database file for pipeline tests."""
    db_file = tmp_path / "test_pipeline.db"
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


def _create_test_image_bytes(
    color: tuple[int, int, int] = (255, 255, 255),
    size: tuple[int, int] = (200, 200),
    fmt: str = "PNG",
) -> bytes:
    """Helper creating raw image bytes for unit testing."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_validate_image_bytes_valid() -> None:
    """Ensure valid image bytes pass validation without error."""
    valid_bytes = _create_test_image_bytes()
    validate_image_bytes(valid_bytes, "document.png")


def test_validate_image_bytes_empty() -> None:
    """Ensure empty bytes trigger a ValidationError."""
    with pytest.raises(ValidationError, match="empty"):
        validate_image_bytes(b"", "empty.jpg")


def test_validate_image_bytes_unsupported_extension() -> None:
    """Ensure unsupported file extensions trigger a ValidationError."""
    valid_bytes = _create_test_image_bytes()
    with pytest.raises(ValidationError, match="Unsupported file format"):
        validate_image_bytes(valid_bytes, "document.txt")


def test_validate_image_bytes_corrupt() -> None:
    """Ensure corrupted byte payload triggers a ValidationError."""
    corrupt_bytes = b"not_a_real_image_payload_header"
    with pytest.raises(ValidationError, match="Corrupt or unreadable"):
        validate_image_bytes(corrupt_bytes, "corrupt.jpg")


def test_compute_image_hash() -> None:
    """Ensure identical image bytes produce identical SHA-256 hashes."""
    b1 = _create_test_image_bytes(color=(100, 100, 100))
    b2 = _create_test_image_bytes(color=(100, 100, 100))
    b3 = _create_test_image_bytes(color=(200, 200, 200))

    assert compute_image_hash(b1) == compute_image_hash(b2)
    assert compute_image_hash(b1) != compute_image_hash(b3)


def test_process_sample_receipt_offline() -> None:
    """Test full pipeline on a real sample receipt image using offline OCR engine."""
    sample_path = (
        Path(__file__).resolve().parent.parent / "sample_data" / "receipt_2.png"
    )
    assert sample_path.exists(), "Sample receipt image must exist"

    with open(sample_path, "rb") as f:
        image_bytes = f.read()

    result = process_single_image(
        image_bytes=image_bytes,
        filename="test_run_receipt_2.png",
        doc_type="receipt_invoice",
        preferred_engine="ocr",
        auto_save=True,
    )

    assert result.status in (DocumentStatus.PROCESSED.value, DocumentStatus.PENDING.value)
    assert result.document_id is not None
    assert result.doc_type in ("receipt_invoice", "receipts")
    assert result.image_hash != ""
    assert result.engine_used in ("ocr", "EasyOCR")
    assert result.is_duplicate is False


def test_duplicate_image_detection() -> None:
    """Ensure re-submitting identical image returns duplicate flag and warning."""
    sample_path = (
        Path(__file__).resolve().parent.parent / "sample_data" / "receipt_2.png"
    )
    with open(sample_path, "rb") as f:
        image_bytes = f.read()

    # First submission
    res1 = process_single_image(
        image_bytes=image_bytes,
        filename="receipt_first.png",
        doc_type="receipt_invoice",
        preferred_engine="ocr",
        auto_save=True,
    )
    assert res1.is_duplicate is False

    # Second submission of identical image
    res2 = process_single_image(
        image_bytes=image_bytes,
        filename="receipt_second.png",
        doc_type="receipt_invoice",
        preferred_engine="ocr",
        auto_save=True,
    )

    assert res2.is_duplicate is True
    assert len(res2.warnings) > 0
    assert "Duplicate image" in res2.warnings[0]


def test_batch_process_images_generator() -> None:
    """Test generator yielding ProcessResult for batch files."""
    img1 = _create_test_image_bytes(color=(10, 20, 30))
    img2 = _create_test_image_bytes(color=(40, 50, 60))

    batch = [(img1, "batch1.png"), (img2, "batch2.png")]
    results = list(
        batch_process_images(
            batch, doc_type="generic_table", preferred_engine="ocr"
        )
    )

    assert len(results) == 2
    assert results[0].filename == "batch1.png"
    assert results[1].filename == "batch2.png"
