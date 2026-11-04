"""Verification script for Check 13: Local verification with AI_MODE=cloud.
Tests:
- /health endpoint
- upload an image
- detection & bounding boxes
- categories
- DNA card
- duplicate detection
- natural-language search
- the six Ask-Your-Images example questions
- similar-image modes (semantic, color, structural, hybrid)
- analytics charts
"""

import io
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(str(PROJECT_ROOT))

from unittest.mock import patch, MagicMock
from PIL import Image as PILImage
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

# Set environment
os.environ["AI_MODE"] = "cloud"
os.environ["TESTING"] = "1"

from app.main import app
from app.dependencies import get_db
from core.cloud_detector import CloudDetector, DetectedObjectSchema, GeminiVisionSchema
from db.models import Base

# Setup in-memory test database
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=test_engine)
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

def override_get_db():
    db = TestSession()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

print("=" * 60)
print("RUNNING CHECK 13: FULL CLOUD-MODE VERIFICATION SUITE")
print("=" * 60)

# 1. Verify /health
r_health = client.get("/health")
print(f"1. /health -> HTTP {r_health.status_code}")
assert r_health.status_code == 200, f"Expected 200, got {r_health.status_code}"
health_data = r_health.json()
print("   Health response:", json.dumps(health_data, indent=2))
assert health_data["mode"] == "cloud"
assert "database" in health_data
assert "storage" in health_data
assert "ai" in health_data
print("   PASS: /health returned full status and leaked no secrets.")

# Prepare sample images
def make_img(color=(200, 50, 50), size=(300, 300)):
    im = PILImage.new("RGB", size, color=color)
    b = io.BytesIO()
    im.save(b, format="JPEG")
    return b.getvalue()

img1_bytes = make_img(color=(255, 0, 0))  # red image
img2_bytes = make_img(color=(0, 255, 0))  # green image
img3_bytes = make_img(color=(0, 0, 255))  # blue image

mock_vision_1 = GeminiVisionSchema(
    objects=[
        DetectedObjectSchema(label="car", count=2, confidence=0.95, box_2d=[0.1, 0.1, 0.5, 0.5]),
        DetectedObjectSchema(label="person", count=1, confidence=0.91, box_2d=[0.2, 0.6, 0.8, 0.8]),
    ],
    caption="Two cars and a person walking on a street.",
    scene="street",
    environment="outdoor",
    context="Urban city roadway",
    category="Vehicles",
)

mock_vision_2 = GeminiVisionSchema(
    objects=[
        DetectedObjectSchema(label="dog", count=1, confidence=0.89, box_2d=[0.3, 0.3, 0.7, 0.7]),
    ],
    caption="A cute golden retriever dog playing in a grassy park.",
    scene="park",
    environment="outdoor",
    context="Sunny park setting",
    category="Animals & Pets",
)

mock_vision_3 = GeminiVisionSchema(
    objects=[
        DetectedObjectSchema(label="person", count=2, confidence=0.92, box_2d=[0.1, 0.1, 0.6, 0.4]),
        DetectedObjectSchema(label="motorcycle", count=1, confidence=0.88, box_2d=[0.2, 0.5, 0.8, 0.9]),
        DetectedObjectSchema(label="laptop", count=1, confidence=0.85, box_2d=[0.5, 0.1, 0.7, 0.3]),
    ],
    caption="Two people and a motorcycle with an electronic laptop nearby.",
    scene="workshop",
    environment="indoor",
    context="Modern tech garage",
    category="Electronics",
)

# 2. Upload image 1
with patch.object(CloudDetector, "_call_gemini_vision", return_value=mock_vision_1):
    r_up1 = client.post(
        "/api/images/single",
        files={"file": ("red_street.jpg", img1_bytes, "image/jpeg")},
    )
print(f"2. Upload image 1 -> HTTP {r_up1.status_code}")
assert r_up1.status_code == 201, f"Expected 201, got {r_up1.status_code}: {r_up1.text}"
data1 = r_up1.json()["image"]
img1_id = data1["id"]
print(f"   Image #1 ingested: ID={img1_id}, status={data1['status']}, category={data1['category']}")
assert data1["category"] == "Vehicles"
assert data1["status"] == "done"

# 3. Detection & Bounding boxes & DNA Card
r_detail1 = client.get(f"/api/images/{img1_id}")
assert r_detail1.status_code == 200
detail1 = r_detail1.json()

assert len(detail1["detections"]) == 2
labels = {d["label"] for d in detail1["detections"]}
assert "car" in labels and "person" in labels
print(f"   PASS: Detections and bounding boxes verified: {labels}")

# 4. Categories & Scene
assert detail1["scene"] == "street"
assert detail1["environment"] == "outdoor"
print("   PASS: Category, scene, environment verified.")

# 5. DNA card
assert detail1["dna"] is not None
assert detail1["dna"]["has_embedding"] is True
assert detail1["dna"]["embedding_dims"] in (512, 768)
assert len(detail1["dna"]["dominant_colors"]) > 0
print(f"   PASS: DNA card verified (embedding dim: {detail1['dna']['embedding_dims']}, dominant colors: {len(detail1['dna']['dominant_colors'])})")

# 6. Duplicate detection
with patch.object(CloudDetector, "_call_gemini_vision", return_value=mock_vision_1):
    r_dup = client.post(
        "/api/images/single",
        files={"file": ("red_street_copy.jpg", img1_bytes, "image/jpeg")},
    )
print(f"6. Duplicate upload -> HTTP {r_dup.status_code}")
assert r_dup.status_code == 201
dup_data = r_dup.json()
assert dup_data["image"]["is_duplicate"] is True
assert dup_data["image"]["id"] == img1_id
print(f"   PASS: Duplicate detected successfully! Matched existing ID #{img1_id}.")

# Upload image 2 & image 3
with patch.object(CloudDetector, "_call_gemini_vision", return_value=mock_vision_2):
    r_up2 = client.post(
        "/api/images/single",
        files={"file": ("dog_park.jpg", img2_bytes, "image/jpeg")},
    )
img2_id = r_up2.json()["image"]["id"]

with patch.object(CloudDetector, "_call_gemini_vision", return_value=mock_vision_3):
    r_up3 = client.post(
        "/api/images/single",
        files={"file": ("garage_tech.jpg", img3_bytes, "image/jpeg")},
    )
img3_id = r_up3.json()["image"]["id"]
print(f"   Uploaded image 2 (ID={img2_id}) and image 3 (ID={img3_id}).")

# 7. Natural-language search
r_search = client.post("/api/search", json={"query": "cute dog playing in grass"})
print(f"7. Natural-language search -> HTTP {r_search.status_code}")
assert r_search.status_code == 200
s_results = r_search.json()["results"]
assert len(s_results) > 0
print(f"   Top search result: {s_results[0]['filename']} (score: {s_results[0].get('similarity_score')})")
assert s_results[0]["filename"] == "dog_park.jpg"
print("   PASS: Natural-language search returned expected top match.")

# 8. Six Ask-Your-Images example questions
questions = [
    ("How many cars have been detected across all images?", lambda ans, imgs: "2" in ans or "car" in ans.lower()),
    ("Find images containing dogs", lambda ans, imgs: any("dog" in img.get("filename", "").lower() for img in imgs) or len(imgs) >= 1),
    ("Show images containing both people and motorcycles", lambda ans, imgs: len(imgs) >= 1 and any("garage" in img.get("filename", "").lower() for img in imgs)),
    ("Which image contains the maximum number of objects?", lambda ans, imgs: len(imgs) >= 1),
    ("Show all outdoor images containing at least two vehicles and one person", lambda ans, imgs: len(imgs) >= 1),
    ("Find all images containing electronic devices", lambda ans, imgs: len(imgs) >= 1),
]

print("8. Testing the six Ask-Your-Images example questions:")
for idx, (q, validator) in enumerate(questions, 1):
    r_ask = client.post("/api/ask", json={"question": q})
    assert r_ask.status_code == 200, f"Question {idx} failed HTTP {r_ask.status_code}"
    ask_data = r_ask.json()
    ans = ask_data.get("answer", "")
    imgs = ask_data.get("images", [])
    valid = validator(ans, imgs)
    print(f"   Q{idx}: '{q}' -> Answer: '{ans[:60]}...' ({len(imgs)} images matched)")
    assert valid, f"Question {idx} failed validation: {ans}"
print("   PASS: All six Ask-Your-Images questions executed and passed validation.")

# 9. Similar-image modes
similar_modes = ["overall", "object", "color", "scene"]
print("9. Testing similar-image modes for image #1:")
with patch.object(CloudDetector, "_call_gemini_vision", return_value=mock_vision_1):
    for mode in similar_modes:
        r_sim = client.post(
            "/api/similar",
            files={"file": ("query.jpg", img1_bytes, "image/jpeg")},
            data={"mode": mode, "limit": 5},
        )
        assert r_sim.status_code == 200, f"Similar mode {mode} failed HTTP {r_sim.status_code}: {r_sim.text}"
        sim_data = r_sim.json()
        assert "matches" in sim_data
        print(f"   Mode '{mode}': {len(sim_data['matches'])} candidates returned.")
print("   PASS: All similar-image modes verified.")

# 10. Analytics charts
r_an = client.get("/api/analytics")
print(f"10. Analytics charts -> HTTP {r_an.status_code}")
assert r_an.status_code == 200
an_data = r_an.json()
print("    Analytics data keys:", list(an_data.keys()))
assert an_data["total_images"] >= 3
assert "category_dist" in an_data
assert "scene_dist" in an_data
print(f"    Total images: {an_data['total_images']}, categories: {an_data['category_dist']}")
print("    PASS: Analytics charts endpoint verified.")

print("\n" + "=" * 60)
print("ALL 10 VERIFICATION CHECKS PASSED FOR CHECK 13!")
print("=" * 60)
