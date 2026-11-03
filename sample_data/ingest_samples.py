"""Ingests generated sample images into the PixelMind database.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.session import get_db_session, init_db
from app.services.image_service import ImageService

SAMPLE_DIR = Path(__file__).resolve().parent

SAMPLE_FILES = [
    "street_cars.png",
    "city_pedestrians.png",
    "park_dog.png",
    "office_workspace.png",
    "living_room.png",
    "kitchen_appliances.png",
    "sports_cyclist.png",
    "nature_wildlife.png",
    "motorcycle_street.png",
    "dining_pizza.png",
    "electronics_multimedia.png",
    "crowded_transit.png",
]


def ingest_all_samples() -> None:
    """Initialize DB and ingest all sample images."""
    print("Initializing database...")
    init_db()

    with get_db_session() as session:
        service = ImageService(session)
        for fname in SAMPLE_FILES:
            fpath = SAMPLE_DIR / fname
            if not fpath.exists():
                print(f"Skipping {fname} (not found)")
                continue

            print(f"Ingesting {fname}...")
            file_bytes = fpath.read_bytes()
            try:
                img, is_dup, msg = service.ingest_image(
                    filename=fname,
                    file_bytes=file_bytes,
                    confidence_threshold=0.25,
                )
                print(f"  -> ID #{img.id}: {img.filename} | Category: {img.category} | Scene: {img.scene} | {msg}")
            except Exception as exc:
                print(f"  -> Error ingesting {fname}: {exc}")

    print("Sample ingestion complete.")


if __name__ == "__main__":
    ingest_all_samples()
